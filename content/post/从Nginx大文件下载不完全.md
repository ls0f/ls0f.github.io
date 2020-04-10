
+++
date = "2020-04-10"
draft = false
title = "从Nginx下载大文件不完整"

+++

# 背景

业务反馈下载一个7GB左右的大文件，总是下载一个到1GB左右就断掉了。

# 分析

在机器上重试，发现能够稳定重现。

![img](/images/下载1GB失败.jpeg)

用curl去下载：

![img](/images/curl下载失败提示.jpeg)

用IDC机器下载没问题，但是远程办公下载了几次都是失败，怀疑和下载速度相关。

梳理下调用链路：

```
客户端 ---> 我方Nginx ---> 我方后台服务 ---> 被调方Nginx ---> 被调用Tomcat
```

期间怀疑是不是某个网关有问题，把连接断掉了。

但在我方后台服务的日志中发现了下面这行：
```
httputil: ReverseProxy read error during body copy: unexpected EOF
```
说明我方服务是没问题的，被调方的Nginx关掉了连接。

为了简化问题，我直接访问被调方Nginx，然后限速下载，问题重现了：

![img](/images/限速下载失败.jpeg)

在机器上抓包，发现确实是对方Nginx关闭了连接。

![img](/images/对方Nginx关闭连接.jpeg)

对方Nginx的errlog里面看到下面日志：

```
2020/03/16 19:50:31 [error] 20256#20256: *697535933 upstream prematurely closed connection while reading upstream, client: x.x.x.x, server: xxx.com"
```
说明是Tomcat关掉了连接。

至此问题有点卡主了，为什么Tomcat会关闭掉连接呢？  
因为没有对方机器权限，调试看日志抓包比来比较麻烦，问题暂且搁置了。

这个问题一直搁置在脑袋里面回想，突然意识到为什么不是我方Nginx断掉连接呢？  
意识到我在Nginx加了一个配置`proxy_request_buffering`，即关掉请求buffer，不将读缓存到磁盘。我方Nginx和后端服务都是读多少传多少，不缓存。  

猜测对方Nginx应该没有这个配置，在慢网络下载中，对方Nginx从Tomcat后端下载很快，所以Nginx会很快将缓存文件写满，之后Nginx不再去Tomcat读，Tomcat将socket缓冲区写满后，就会触发写超时（默认60s），关闭连接。

向对方确认，确实配置了`proxy_max_temp_file_size 128m`，用curl限速2M去下载，只能下载135M左右是能解释通的。

用相关关键词搜索了下有一个关于这个case的ticket（见参考链接）：

>The 1GB limit suggests that the problem is due to ​proxy_max_temp_file_size. It is one gigabyte by default, and if the limit is reached, nginx will stop reading from the backend till all disk-buffered data are sent to the client. This in turn can result in a send timeout on the backend side.

>Please check nginx and your backend logs to see what happens here. Likely there are something like "upstream prematurely closed connection" in nginx error log, and send timeouts in your backend logs. Alternatively, just check if proxy_max_temp_file_size 0; helps (this will disable disk buffering completely).

解决方案是：
>* Tune proxy_max_temp_file_size. Consider either configuring the limit above the size of all expected responses, or small enough for your backend to don't time out. In particular, proxy_max_temp_file_size 0; might be a good choice when proxying large files.
> * Tune your backend timeouts appropriately.

# 参考
* https://www.jfrog.com/jira/browse/RTFACT-16743
* https://trac.nginx.org/nginx/ticket/1472


