+++
date = "2019-12-04"
draft = false
title = "Requests连接CLOSE_WAIT"

+++

线上Python后台服务出现了一些CLOSE_WAIT状态的TCP连接，看连接的dst ip，都是requests库发出的请求。

![img](/images/close_wait.png)

首先要知道CLOSE_WAIT的状态的连接是因为对方已经关闭连接，我方还没有调用close关闭连接。
由于使用了reqeusts 的seesion，会有连接池，requests这么完善的http库，不太可能出现连接泄露的问题。  
于是大胆猜测：  
>requests 不会主动去探测所有连接是否可用，当从连接池取出连接的时候，再去测试连接是否关闭，存在的CLOSE_WAIT的连接为正常现象，
当下一次连接被重用的时候，会被检测已断开然后再主动关闭。

看代码，requests的请求发送以及连接池其实是urllib3来提供的。

首先看下如何从连接池获取可用连接的:
https://github.com/urllib3/urllib3/blob/master/src/urllib3/connectionpool.py#L237
```
    def _get_conn(self, timeout=None):
        """
        Get a connection. Will return a pooled connection if one is available.
        If no connections are available and :prop:`.block` is ``False``, then a
        fresh connection is returned.
        :param timeout:
            Seconds to wait before giving up and raising
            :class:`urllib3.exceptions.EmptyPoolError` if the pool is empty and
            :prop:`.block` is ``True``.
        """
        conn = None
        try:
            conn = self.pool.get(block=self.block, timeout=timeout)

        except AttributeError:  # self.pool is None
            raise ClosedPoolError(self, "Pool is closed.")

        except queue.Empty:
            if self.block:
                raise EmptyPoolError(
                    self,
                    "Pool reached maximum size and no more connections are allowed.",
                )
            pass  # Oh well, we'll create a new connection then

        # If this is a persistent connection, check if it got disconnected
        if conn and is_connection_dropped(conn):
            log.debug("Resetting dropped connection: %s", self.host)
            conn.close()
            if getattr(conn, "auto_open", 1) == 0:
                # This is a proxied connection that has been mutated by
                # httplib._tunnel() and cannot be reused (since it would
                # attempt to bypass the proxy)
                conn = None

        return conn or self._new_conn()
```
关键点在 https://github.com/urllib3/urllib3/blob/master/src/urllib3/connectionpool.py#L265
```
        if conn and is_connection_dropped(conn):
            log.debug("Resetting dropped connection: %s", self.host)
            conn.close()
            if getattr(conn, "auto_open", 1) == 0:
                # This is a proxied connection that has been mutated by
                # httplib._tunnel() and cannot be reused (since it would
                # attempt to bypass the proxy)
                conn = None

        return conn or self._new_conn()
```
取出连接后，会去判断连接是否断掉，我们看下他如何判断的：
https://github.com/urllib3/urllib3/blob/bffbde720c060c396d6b3bc396579d4f98c8fa70/src/urllib3/util/connection.py#L7
```
def is_connection_dropped(conn):  # Platform-specific
    """
    Returns True if the connection is dropped and should be closed.
    :param conn:
        :class:`httplib.HTTPConnection` object.
    Note: For platforms like AppEngine, this will always return ``False`` to
    let the platform handle connection recycling transparently for us.
    """
    sock = getattr(conn, "sock", False)
    if sock is False:  # Platform-specific: AppEngine
        return False
    if sock is None:  # Connection already closed (such as by httplib).
        return True
    try:
        # Returns True if readable, which here means it's been dropped
        return wait_for_read(sock, timeout=0.0)
    except NoWayToWaitForSocketError:  # Platform-specific: AppEngine
        return False
```
wait_for_socket 函数包装了很多层，追踪下面这个就好：
https://github.com/urllib3/urllib3/blob/bffbde720c060c396d6b3bc396579d4f98c8fa70/src/urllib3/util/wait.py#L127
我们以select_wait_for_socket为例：
https://github.com/urllib3/urllib3/blob/bffbde720c060c396d6b3bc396579d4f98c8fa70/src/urllib3/util/wait.py#L71
```
def select_wait_for_socket(sock, read=False, write=False, timeout=None):
    if not read and not write:
        raise RuntimeError("must specify at least one of read=True, write=True")
    rcheck = []
    wcheck = []
    if read:
        rcheck.append(sock)
    if write:
        wcheck.append(sock)
    # When doing a non-blocking connect, most systems signal success by
    # marking the socket writable. Windows, though, signals success by marked
    # it as "exceptional". We paper over the difference by checking the write
    # sockets for both conditions. (The stdlib selectors module does the same
    # thing.)
    fn = partial(select.select, rcheck, wcheck, wcheck)
    rready, wready, xready = _retry_on_intr(fn, timeout)
    return bool(rready or wready or xready)
```
以非阻塞方式将这个连接的fd传给select去检测是否可读，如果这个返回的可读fd列表非空（正常上一个请求的body读完后就不可读了，如果可读说明读到的是EOF），说明这个连接已经被对方关闭了。  
至此，说明猜测是对的。