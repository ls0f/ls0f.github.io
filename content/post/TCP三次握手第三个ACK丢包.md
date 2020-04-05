+++
date = "2020-04-05"
draft = false
title = "TCP握手第三个ACK丢包会怎么样"

+++

问题：TCP三次握手过程中，第三个ACK网络丢包了会怎么样？

首先看一下三次握手的流程：

![img](/images/tcpopen3way.png)

客户端在发送第三个ACK后，已经进入了`establish`状态，如果这个ACK在网络中丢失了，此时服务端还处于`syn-received`状态。

分两种情况：
* 客户端连接建立后，不发送数据
* 客户端连接建立后，立马发送数据

为了模拟第三个ACK丢失的情况，我在本地运行了`python -m SimpleHTTPServer`监听8000端口。  
利用iptables来模拟ACK丢包
```
# 清掉iptables规则
iptables -F
# PSH包需要放行
iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8000 --tcp-flags PSH PSH -j ACCEPT
iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8000 --tcp-flags ACK ACK -j DROP
```

用telnet来连接服务端，但是不发送数据：
![img](/images/ack_lost.jpeg)
抓包可以看到，ACK丢失触发了服务端的SYN/ACK重传。（为了防止SYN flood攻击，有些网站关闭了SYN/ACK重传，比如baidu）

用curl来请求服务器：
![img](/images/ack_lost_with_curl.jpeg)
图片可以看到，握手的第三个ACK包虽然丢了，但是接下来的一个数据包设置了ACK位，服务端还是能握手成功，并且正常响应curl请求。

如果接下来的第一个数据包也丢了会怎么样呢？，我用raw socket去发包模拟验证了下，代码放在[这里](https://gist.github.com/ls0f/941912ca0cf6e756eeb4524e497a7095)

注意用raw socket去发包的话，需要关闭掉tcp协议栈默认回的RST包：
```
iptables -F
iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8000 --tcp-flags RST RST -j DROP
```

![img](/images/out_of_order.jpeg)
PS:*图片标注有问题，其实是先发了包2（模拟包1丢了），再发的包1，wireshark可以看出包的顺序有问题*

即使接下来第一个包丢了也没关系，只要后面的包带上正确的ACK就能握手成功，能够正确重传丢失的包，请求都可以正常返回。当然如果第一个ACK错误了，肯定会收到服务端的RST。

![img](/images/wrong_ack.jpeg)

结论：

TCP设计的健壮性，第三个ACK丢包后也不影响后续连接的使用。


