import socket
import threading
import hashlib
import argparse

# Globals
# IP_ADDRESS = socket.gethostbyname(socket.gethostname())
IP_ADDRESS = '192.168.137.1'
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


def join_me(node, known_port):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(known_port)))
	# Is there only 1 node in DHT right now?
	s.send('ARE_YOU_ALONE'.encode('utf-8'))
	msg = s.recv(BUFFER_SIZE).decode('utf-8')
	if msg == 'YES':
		node.successor = known_port
		node.predeccessor = known_port
		msg = 'UPDATE_SUCCESSOR_AND_PREDECESSOR'
		s.send(msg.encode('utf-8'))
		msg = s.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ACK':
			s.send(str(node.port).encode('utf-8'))
		s.close()

	elif msg == 'NO':
		s.send('SEND_ME_PREDECESSOR'.encode('utf-8'))
		other_pred_port = int(s.recv(BUFFER_SIZE).decode('utf-8'))
		other_key = hash_func(IP_ADDRESS+str(known_port))
		other_pred_key = hash_func(IP_ADDRESS+str(other_pred_port))

		if (node.key < other_key) and (((node.key > other_pred_key) and (other_key > other_pred_key)) or ((node.key < other_pred_key) and (other_key < other_pred_key))):
			actual_join(s, node, known_port, other_pred_port)

		elif (node.key > other_key) and (other_pred_key > other_key) and (node.key > other_pred_key):
			actual_join(s, node, known_port, other_pred_port)

		else:
			s.send('SEND_ME_SUCCESSOR'.encode('utf-8'))
			other_succ_port = int(s.recv(BUFFER_SIZE).decode('utf-8'))
			s.close()
			join_me(node, other_succ_port)


def set_second_successor(node):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(node.successor)))
	s.send('SEND_ME_SUCCESSOR'.encode('utf-8'))
	node.second_successor = int(s.recv(BUFFER_SIZE).decode('utf-8'))
	s.close()


def actual_join(s, node, known_port, other_pred_port):
	s.send('I_AM_YOUR_PREDECESSOR'.encode('utf-8'))
	msg = s.recv(BUFFER_SIZE).decode('utf-8')
	if msg == 'ACK':
		s.send(str(node.port).encode('utf-8'))
		node.successor = known_port
		s.close()

	another_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	another_socket.connect((IP_ADDRESS, int(other_pred_port)))
	another_socket.send('I_AM_YOUR_SUCCESSOR'.encode('utf-8'))
	msg = another_socket.recv(BUFFER_SIZE).decode('utf-8')
	another_socket.send(str(node.port).encode('utf-8'))
	node.predeccessor = other_pred_port
	# Update the second successor of predecessor as well
	msg = another_socket.recv(BUFFER_SIZE).decode('utf-8')
	another_socket.send(str(node.successor).encode('utf-8'))
	another_socket.close()


def client_thread(node):
	while True:
		option = input('Enter 1 to print links:\n')
		if option == '1':
			node.print_information();
		else:
			continue


def server_thread(this_node, conn):
	while True:
		msg = conn.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ARE_YOU_ALONE':
			if (this_node.successor == this_node.port) and (this_node.predeccessor == this_node.port):
				conn.send('YES'.encode('utf-8'))
			else:
				conn.send('NO'.encode('utf-8'))
				continue

		if msg == 'UPDATE_SUCCESSOR_AND_PREDECESSOR':
			conn.send('ACK'.encode('utf-8'))
			other_port = (conn.recv(BUFFER_SIZE)).decode('utf-8')
			this_node.predeccessor = other_port
			this_node.successor = other_port

		if msg == 'I_AM_YOUR_PREDECESSOR':
			conn.send('ACK'.encode('utf-8'))
			port = int(conn.recv(BUFFER_SIZE).decode('utf-8'))
			this_node.predeccessor = port

		if msg == 'I_AM_YOUR_SUCCESSOR':
			conn.send('ACK'.encode('utf-8'))
			port = int(conn.recv(BUFFER_SIZE).decode('utf-8'))
			this_node.successor = port
			# Update 2nd successor as well
			conn.send('ACK'.encode('utf-8'))
			ss = int(conn.recv(BUFFER_SIZE).decode('utf-8'))
			this_node.second_successor = ss

		if msg == 'SEND_ME_SUCCESSOR':
			conn.send(str(this_node.successor).encode('utf-8'))

		if msg == 'SEND_ME_PREDECESSOR':
			conn.send(str(this_node.predeccessor).encode('utf-8'))

		if msg == 'UPDATE_SECOND_SUCCESSOR':
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((IP_ADDRESS, int(this_node.successor)))
			s.send('SEND_ME_SUCCESSOR'.encode('utf-8'))
			this_node.second_successor = int(s.recv(BUFFER_SIZE).decode('utf-8'))
			s.close()


def update_second_seccessor(node):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(node.predeccessor)))
	s.send('SEND_ME_PREDECESSOR'.encode('utf-8'))
	pre_pred = int(s.recv(BUFFER_SIZE).decode('utf-8'))
	s.close()

	# If there are 2 nodes in DHT, a node will try to connect to itself to update 2nd successor
	# Don't let that happen
	if (node.port != pre_pred):
		another_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		another_socket.connect((IP_ADDRESS, int(pre_pred)))
		another_socket.send('UPDATE_SECOND_SUCCESSOR'.encode('utf-8'))
		another_socket.close()


def main():
	parser = argparse.ArgumentParser(description='Join DHT. ')
	parser.add_argument('port', type=int, nargs=1)
	args = parser.parse_args()

	port = args.port[0]
	node = Node(port)
	print('My key is:', node.key)

	other_port = input('Enter port of any known node, leave blank otherwise: ')
	if (port == other_port) or (int(port) > 65535) or (int(port) < 0):
		print('What are you doing?')
		return
	if other_port:
		join_me(node, other_port)
		set_second_successor(node)
		update_second_seccessor(node)

	t = threading.Thread(target=client_thread, args=(node,))
	t.daemon = True
	t.start()

	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.bind((IP_ADDRESS, port))
	s.listen()
	while True:
		conn, address = s.accept()
		t = threading.Thread(target=server_thread, args=(node, conn))
		t.daemon = True
		t.start()
	s.close()

if __name__ == '__main__':
    main()
