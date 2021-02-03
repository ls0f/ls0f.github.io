+++
date = "2021-02-03"
draft = false
title = "TCP连接超时"

+++

# 背景

线上Nginx服务突然报错，日志打印Connection timed out

# 排查

首先看一下完整日志
```
connect() failed (110: Connection timed out) while connecting to upstream ....
```

**说明在三次握手阶段没有收到对方的SYN+ACK包**  
用ping和curl确定网络没问题后，猜测是对方丢掉了SYN包

### dmesg

在目标服务机器上执行dmesg，有提示`Possible SYN flooding on port 7000`，正是程序监听端口， 说明TCP半连接队列已经满了。 
```
root@admin:~# dmesg | tail
[22430720.630480] [20643]     0 20643    27755      158      14        0            -1 sleep
[22430720.630489] Memory cgroup out of memory: Kill process 43283 (git) score 558 or sacrifice child
[22430720.630769] Killed process 42232 (git) total-vm:10054400kB, anon-rss:9657832kB, file-rss:1268kB
[22571596.273737] ipip: IPv4 over IPv4 tunneling driver
[25764018.180814] Netfilter messages via NETLINK v0.30.
[33672504.427518] NOHZ: local_softirq_pending 200
[33724865.250280] NOHZ: local_softirq_pending 200
[33887343.649246] TCP: TCP: Possible SYN flooding on port 7000. Sending cookies.  Check SNMP counters.
[33887464.685796] TCP: TCP: Possible SYN flooding on port 7000. Sending cookies.  Check SNMP counters.
[35738682.087444] NOHZ: local_softirq_pending 200
```

### netstat
执行命令`watch -n 1 "netstat -s  | grep LISTEN"`，被丢弃的SYN包一直在增加，说明发生了丢包
```
3161232 SYNs to LISTEN sockets dropped
```
用TcpExtListenOverflows和TcpExtListenDrops指标更直观  
```
nstat -az | grep -E 'TcpExtListenOverflows|TcpExtListenDrops'
```
什么情况会发生SYN丢包？

### TCP连接队列

Linux2.2之后，TCP有两个连接队列


![img](https://blog.cloudflare.com/content/images/2018/01/all-1.jpeg)

* The SYN Queue（半连接队列）
* The Accept Queue（等待应用层ACCEPT）

半连接队列保存的是SYN-Receive状态的连接，并负责超时的时候重传SYN+ACK(重传次数/proc/sys/net/ipv4/tcp_synack_retries    
半连接队列大小计算比较复杂 

Accept Queue保存的是ESTABLISH状态的连接，队列大小等于Min(backlog, /proc/sys/net/core/somaxconn/proc/sys/net/core/somaxconn)

收到SYN时:

* 如果SYN Queue满
  * 如果net.ipv4.tcp_syncookies=0，会直接丢弃
  * 否则输出 "possible SYN flooding on port %d. Sending cookies. Check SNMP counters"
* 如果Accept Queue满并且qlen_young(未重传过的半连接数量)的值大于1则直接丢弃S 

收到ACK时:
* 如果Accept Queue满：
  * tcp_abort_on_overflow=1,则TCP协议栈回复RST包,该连接从SYN Queue中删除
  * tcp_abort_on_overflow=0,则TCP协议栈将该连接标记为acked ，但仍保留在SYN queue中，并启动 timer以便重发SYN+ACK 包；当 SYN+ACK的重传次数超过 net.ipv4.tcp_synack_retries 设置的值时，再将该连接从SYN Queue中删除；

总结有两种SYN丢包的情况

* SYN Queue满并且net.ipv4.tcp_syncookies=0
* Accept Queue满并且qlen_young>1

服务器上开启了syncookie，说明是Accept Queue满造成的。
```
root@admin:~# sysctl net.ipv4.tcp_syncookies
net.ipv4.tcp_syncookies = 1
```
查看进程的队列情况：（Send-Q表示Accept Queue的大小，Recv-Q 表示其实际大小）
```
ss -plnt sport = :7000|cat
State      Recv-Q Send-Q Local Address:Port               Peer Address:Port              
LISTEN     129      128          *:7000                     *:*              
```
可以看见Accept Queue已经满了。

### 为什么突然报错

看Nginx日志，有比较大的并发请求，后端是多进程同步IO模型，请求处理不过来，造成连接积压Accept Queue满。

**后端服务也须关注SYN丢包情况**

# Ref
https://blog.cloudflare.com/syn-packet-handling-in-the-wild/   
http://veithen.io/2014/01/01/how-tcp-backlog-works-in-linux.html  
https://kingsamchen.github.io/2019/12/21/syn-queue-and-accept-queue/  
https://gohalo.me/post/network-synack-queue.html  
https://www.kernel.org/doc/html/v5.0/networking/snmp_counter.html