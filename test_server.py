import socket
import sys

HOST = sys.argv[1]
PORT = int(sys.argv[2])

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(128)
print "socket buffer:size",s.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
while 1:
    conn, addr = s.accept()
    print "conn buffer:size",conn.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    print('Connected by', addr)
    while True:
        data = conn.recv(1024)
        if not data:
            conn.close()
            break
        print data
