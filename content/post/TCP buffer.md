+++
date = "2020-04-06"
draft = false
title = "TCP Buffer"

+++

看tcp socket buffer size：  
* /proc/sys/net/ipv4/tcp_rmem (for read)
* /proc/sys/net/ipv4/tcp_wmem (for write)  

```
[root@VM_137_43_centos ~]# cat /proc/sys/net/ipv4/tcp_rmem
4096    87380   6291456
[root@VM_137_43_centos ~]# cat /proc/sys/net/ipv4/tcp_wmem
4096    16384   4194304       
```
三个数字分别表示最小、默认、最大的内存限制。 

简单验证下tcp write buffer到底有多大。  
客户端：
```
import socket
import sys
import os
import errno
import time

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)                 
s.connect((sys.argv[1] , int(sys.argv[2])))
s.setblocking(0)
buf = "*" * 1024
cnt = 0
while True:
    try:
        n = s.send(buf)
        cnt += n
        sys.stdout.write("\r send %s bytes, total:%s" % (n, cnt))
        sys.stdout.flush()
        time.sleep(0.2)
    except IOError as err:
        if err.errno == errno.EWOULDBLOCK:
            print
            print("write buffer is full, send %s bytes total" % cnt)
            a = raw_input("enter q to exit:")
            if a == 'q':
                break
    except:
        raise
s.close()
```
服务端：
```
import socket
import sys

HOST = sys.argv[1]  
PORT = int(sys.argv[2])

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(128)
while 1:
    conn, addr = s.accept()
    print('Connected by', addr)
    while True:
        data = conn.recv(1024)
        if not data:
            conn.close()
            break
        print data 
```
为了让客户端buffer写满，服务端需要在s.accept()后打上断点，不读客户端数据。  

服务端可以用`python -m pdb test_server.py 127.0.0.1 1234`运行。   
客户端`python test_client.py 127.0.0.1 1234` 。    

客户端观察到： 
```
write buffer is full, send 696704 bytes total
```
说明发送了696704字节后数据，调用write开始阻塞，buffer写满了。  

wireshark抓包：  

![img](/images/tcp_buffer_last_ack.jpeg)
服务端最后的ACK是322561，说明客户端的写buffer里面至少还有696704-322560=374144字节的数据，同理也可以知道服务端的读buffer至少有322560个字节已经ACK过的数据。

参考：  
* [how-to-find-the-socket-buffer-size-of-linux](https://stackoverflow.com/questions/7865069/how-to-find-the-socket-buffer-size-of-linux)