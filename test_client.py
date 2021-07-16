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
        n = 0
        time.sleep(0.2)
    except IOError as err:
        cnt += n
        if err.errno == errno.EWOULDBLOCK:
            print
            print("write buffer is full, send %s bytes total" % cnt)
            a = raw_input("enter q to exit:")
            if a == 'q':
                break
    except:
        raise
s.close()
