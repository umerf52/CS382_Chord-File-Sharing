import socket
import threading
import hashlib
import argparse

# Globals
IP_ADDRESS = socket.gethostbyname(socket.gethostname())
TOTAL_NODES = 30
BASE_16 = 16
BUFFER_SIZE = 1024


class Node:
	def __init__(self, port):
		self.key = hash_func(IP_ADDRESS + str(port))
		self.port = port
		self.successor = port
		self.second_successor = port
		self.predeccessor = port

	def print_information(self):
		print('My key is:', self.key,", with port:", self.port)
		print('My successor\'s key is:', hash_func(IP_ADDRESS+str(self.successor)),", with port:", self.successor)
		print('My second successors\'s key is:', hash_func(IP_ADDRESS+str(self.second_successor)),", with port:", self.second_successor)
		print('My predecessor\'s key is:', hash_func(IP_ADDRESS+str(self.predeccessor)),", with port:", self.predeccessor, '\n')


def hash_func(value):
	value = value.encode('utf-8')
	return int(hashlib.sha1(value).hexdigest(), BASE_16) % TOTAL_NODES

def join_one(this_node, other_port):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.bind((IP_ADDRESS, other_port))

def join_me(node, known_port):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(known_port)))
	s.send('ARE_YOU_ALONE'.encode('utf-8'))
	msg = s.recv(BUFFER_SIZE).decode('utf-8')
	if msg == 'YES':
		node.successor = known_port
		node.predeccessor = known_port
		print('Updated my successor and predeccessor\n')
		msg = 'UPDATE_SUCCESSOR_AND_PREDECESSOR'
		s.send(msg.encode('utf-8'))
		msg = s.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ACK'+'UPDATE_SUCCESSOR_AND_PREDECESSOR':
			s.send(str(node.port).encode('utf-8'))
		s.close()
	else if msg == 'NO':
		other_key = hash_func(IP_ADDRESS+known_port)
		if other_key > hash_func(IP_ADDRESS+str(node.successor)):
			pass


def server_thread(this_node, conn):
	while True:
		msg = conn.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ARE_YOU_ALONE':
			if (this_node.successor == this_node.port) and (this_node.predeccessor == this_node.port):
				conn.send('YES'.encode('utf-8'))
			else:
				conn.send('NO'.encode('utf-8'))

		if msg == 'UPDATE_SUCCESSOR_AND_PREDECESSOR':
			msg = 'ACK'+msg
			conn.send(msg.encode('utf-8'))
			other_port = (conn.recv(BUFFER_SIZE)).decode('utf-8')
			this_node.predeccessor = other_port
			this_node.successor = other_port
			print('Updated my successor and predeccessor\n')
			this_node.print_information()


def main():
	parser = argparse.ArgumentParser(description='Join DHT. ')
	parser.add_argument('port', type=int, nargs=1)
	args = parser.parse_args()

	port = args.port[0]
	node = Node(port)

	other_port = input('Enter port of any known node, leave blank otherwise: ')
	if other_port:
		join_me(node, other_port)

	node.print_information()
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.bind((IP_ADDRESS, port))
	s.listen()
	print('Listening for others to join\n')
	while True:
		conn, address = s.accept()
		t = threading.Thread(target=server_thread, args=(node, conn))
		t.start()
	s.close()

if __name__ == '__main__':
    main()