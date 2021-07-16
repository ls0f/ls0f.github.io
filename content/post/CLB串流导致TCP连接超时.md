+++
date = "2021-07-16"
draft = false
title = "CLB串流导致TCP连接超时"

+++

# 背景

线上Nginx服务突然报错，日志打印Connection timed out

# 排查

首先看一下完整日志
```
connect() failed (110: Connection timed out) while connecting to upstream ....
```

看来是熟悉的味道，和上次的问题一样[TCP连接超时](/post/tcp连接超时/)

于是和对方业务沟通：我们出现SYN丢包了，得检查你们TCP连接队列满了是否有丢包，^_^

对方有5台机器，发现有一台机器确实有SYN丢包问题:  
  
![](/images/syn_loss.png)
  
于是愉快的让对方先将这台机器隔离出来，再观察下情况。  
然鹅第二天业务高峰的时候，还是出现了TCP连接超时。

梳理调用链路:  
`客户端 -> 我方Nginx -> CLB ->对方Nginx ->对方后台服务`  
  
仔细想想，CLB后面挂载的是对方Nginx，这货不太可能出现连接队列满的情况。 难道是网络或者CLB有丢包？

于是和CLB助手沟通丢包问题，对方直接抛出了文档:
```
关于同一个客户端通过不同的中间节点访问同一个后端 RS 的同一个端口时串流问题的说明
问题现象
同一个客户端在同一时刻，通过不同的中间节点访问同一个 RS 的同一个端口会出现串流现象。具体场景如下：

同一个客户端，同时通过同一个 CLB 的四层、七层监听器，访问同一个 RS 的同一个端口。
同一个客户端，同时通过不同 CLB 的不同监听器，访问同一个 RS 的同一个端口。
访问内网 CLB 的客户端比较集中，且后端服务相同时，有较大概率会出现串流。（访问公网 CLB 的客户端来源较广，很少出现串流。）
问题原因
当前 CLB 会透传客户端 IP 到后端 RS，因此会导致 client_ip:client_port -> vip:vport -> rs_ip:rs_port 最终变为 client_ip:client_port --> rs_ip:rs_port
```
检查确实会有可能出现串流问题，我方通过两个CLB访问对方的Nginx，两个CLB都挂载了同样的RS。
`client_ip:client_port -> vip:vport -> rs_ip:rs_port 最终变为 client_ip:client_port --> rs_ip:rs_port`  
  
经过CLB地址转换后，TCP四元组确实会重复，也就是串流。如果串流后，建连的SYN包肯定会被协议栈丢掉。

解决方法: 将2个CLB分别挂载不同的RS

# Ref
[0x01]https://cloud.tencent.com/document/product/214/5411