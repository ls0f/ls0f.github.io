title: 为什么daemon进程fork两次
date: 1970-01-01
comments: true
categories: 

# 为什么daemon进程fork两次

写daemon进程的一版方式为：

```
pid = os.fork()
if pid > 0:
    exit(0)
os.setsid()
...
```

但看网上很多有fork两次的写法：

```
pid = os.fork()
if pid > 0:
    exit(0)
os.setsid()
pid = os.fork()
if pid > 0:
    exit(0)
...
```

我感觉是没必要，第一次fork后，父进程退出了，子进程已经托管给init进程，然后调用setsid成为会话首进程，就已经是daemon进程了。为什么还要调用第二次fork？

看stackoverflow上的[讨论](http://stackoverflow.com/questions/881388/what-is-the-reason-for-performing-a-double-fork-when-creating-a-daemon):

>So why the double fork? POSIX.1-2008 Sec. 11.2.3, "The Controlling Terminal", has the answer (emphasis added):

>>The controlling terminal for a session is allocated by the session leader in an implementation-defined manner. If a session leader has no controlling terminal, and opens a terminal device file that is not already associated with a session without using the O_NOCTTY option (see open()), it is implementation-defined whether the terminal becomes the controlling terminal of the session leader. If a process which is not a session leader opens a terminal file, or the O_NOCTTY option is used on open(), then that terminal shall not become the controlling terminal of the calling process.

>This tells us that if a daemon process does something like this ...

>int fd = open("/dev/console", O_RDWR);
... then the daemon process might acquire /dev/console as its controlling terminal, depending on whether the daemon process is a session leader, and depending on the system implementation. The program can guarantee that the above call will not acquire a controlling terminal if the program first ensures that it is not a session leader.


>Normally, when launching a daemon, setsid is called (from the child process after calling fork) to dissociate the daemon from its controlling terminal. However, calling setsid also means that the calling process will be the session leader of the new session, which leaves open the possibility that the daemon could reacquire a controlling terminal. The double-fork technique ensures that the daemon process is not the session leader, which then guarantees that a call to open, as in the example above, will not result in the daemon process reacquiring a controlling terminal.

第二次fork是为了避免daemon进程不是会话首进程(session leader)，如果是会session leader进程，可能会打开controlling terminal，fork两次实为更保险的做法。如果代码中不会打开`terminal device`，或者打开会带上`O_NOCTTY`，那么一次fork也是行的。


那么daemon进程为什么要避免打开`controlling terminal`呢？[参考这个](http://stackoverflow.com/questions/12079059/why-prevent-a-file-from-opening-as-controlling-terminal-with-o-noctty)

>Having a controlling tty means there are certain conditions where specific signals might be sent to your program in response to things happening on the tty/window where your program is running. If the program is intended to be a daemon, it's generally cleaner to make sure you don't have a controlling tty than it is to try to write code to handle all the extra conditions that you don't really care about to begin with...

也就是说为了避免在代码里面去handler你不关心的外部异常。


网上很多人说两次fork是为了避免僵尸进程，在daemon进程里面可不是这么回事。
比如说写一个web server服务器，主进程用于接收请求，每来一个请求，主进程fork一个子进程来处理，但主进程不能阻塞(wait_pid)，于是子进程再fork一次，子进程退出，init进程成为子进程fork出来的字进程的父进程，主进程将进程的善后工作交给init进程，避免出现僵尸进程。


一个python写的daemon进程例子：[http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/](http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/)