import socket
import threading
import hashlib
import argparse
import os
import time

# Globals
IP_ADDRESS = socket.gethostbyname(socket.gethostname())
# IP_ADDRESS = '192.168.137.1'
TOTAL_NODES = 30
BASE_16 = 16
BUFFER_SIZE = 1024


class Node:
	def __init__(self, port):
		self.key = hash_func(IP_ADDRESS + str(port))
		self.port = port
		self.successor = port
		self.second_successor = port
		self.predecessor = port
		self.file_list = []

	def print_information(self):
		print('My key is:', self.key,", with port:", self.port)
		print('My successor\'s key is:', hash_func(IP_ADDRESS+str(self.successor)),", with port:", self.successor)
		print('My second successors\'s key is:', hash_func(IP_ADDRESS+str(self.second_successor)),", with port:", self.second_successor)
		print('My predecessor\'s key is:', hash_func(IP_ADDRESS+str(self.predecessor)),", with port:", self.predecessor, '\n')

	def print_files(self):
		print('Files at this node are: ')
		for f in self.file_list:
			print(f)
		print('')


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
		node.predecessor = known_port
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
	node.predecessor = other_pred_port
	# Update the second successor of predecessor as well
	msg = another_socket.recv(BUFFER_SIZE).decode('utf-8')
	another_socket.send(str(node.successor).encode('utf-8'))
	another_socket.close()


def node_leaving(node):
	if node.successor == node.port:
		return

	elif node.successor == node.predecessor:
		another_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		another_socket.connect((IP_ADDRESS, int(node.successor)))
		another_socket.send('SUCCESSOR_AND_PREDECESSOR_LEAVING'.encode('utf-8'))
		msg = another_socket.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ACK':
			pass
		another_socket.close()
		return

	else:
		# Tell predecessor
		another_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		another_socket.connect((IP_ADDRESS, int(node.predecessor)))
		another_socket.send('SUCCESSOR_LEAVING'.encode('utf-8'))
		msg = another_socket.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ACK':
			msg = ''
			another_socket.send(str(node.successor).encode('utf-8'))
			msg = another_socket.recv(BUFFER_SIZE).decode('utf-8')
			if msg == 'ACK':
				if node.second_successor == node.port:
					another_socket.send(str(node.successor).encode('utf-8'))
				else:
					another_socket.send(str(node.second_successor).encode('utf-8'))
		another_socket.close()

		# Tell successor
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.connect((IP_ADDRESS, int(node.successor)))
		s.send('PREDECESSOR_LEAVING'.encode('utf-8'))
		msg = s.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ACK':
			msg = ''
			s.send(str(node.port).encode('utf-8'))
			msg = s.recv(BUFFER_SIZE).decode('utf-8')
			if msg == 'ACK':
				s.send(str(node.predecessor).encode('utf-8'))
		s.close()


def initiate_put(node):
	file_name = input('Enter the name of the file you want to "put": ')
	print(' ')

	if os.path.isfile(file_name):
		file_key = hash_func(file_name)
		pred_key = hash_func(IP_ADDRESS + str(node.predecessor))
		if ((file_key < node.key) and ((file_key > pred_key and node.key > pred_key) or (file_key < pred_key and node.key < pred_key))) or (file_key > node.key and pred_key > node.key and file_key > pred_key):
			node.file_list.append(file_name)
			print('File saved')
		else:
			t = threading.Thread(target=put_iterative, args=(file_key, file_name, node.successor, node.port))
			t.daemon = True
			t.start()
	else:
		print('File does not exist')


def put_iterative(file_key, file_name, new_port, original_port):
	temp_key = hash_func(IP_ADDRESS + str(new_port))
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(new_port)))
	s.send('SEND_ME_PREDECESSOR'.encode('utf-8'))
	pred_port = int(s.recv(BUFFER_SIZE).decode('utf-8'))
	pred_key = hash_func(IP_ADDRESS + str(pred_port))

	if ((file_key < temp_key) and ((file_key > pred_key and temp_key > pred_key) or (file_key < pred_key and temp_key < pred_key))) or (file_key > temp_key and pred_key > temp_key and file_key > pred_key):
		s.send('RECEIVE_FILE'.encode('utf-8'))
		msg = s.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ACK':
			msg = ''
			s.send(file_name.encode('utf-8'))
			msg = s.recv(BUFFER_SIZE).decode('utf-8')
			if msg == 'ACK':
				file_size = os.path.getsize(file_name) 
				s.send(str(file_size).encode('utf-8'))
				msg = s.recv(BUFFER_SIZE).decode('utf-8')
				if msg == 'ACK':
					file = open(file_name, 'rb')
					to_send = file.read(BUFFER_SIZE)
					sent = len(to_send)
					s.send(to_send)
					while sent < file_size:
						to_send = file.read(BUFFER_SIZE)
						s.send(to_send)
						sent += len(to_send)
					file.close()
					time.sleep(0.5)
					s.send('FINISHED_SENDING'.encode('utf-8'))
					print(s.recv(BUFFER_SIZE).decode('utf-8'))
		s.close()

	else:
		s.send('SEND_ME_SUCCESSOR'.encode('utf-8'))
		new_port = int(s.recv(BUFFER_SIZE).decode('utf-8'))
		s.close()
		put_iterative(file_key, file_name, new_port, original_port)


def client_thread(node):
	while True:
		option = input('Enter 0 to leave DHT\nEnter 1 to print links\nEnter 2 to "put" a file\nEnter 4 to print available files\n\n')
		if option == '0':
			node_leaving(node)
			os._exit(0)
		elif option == '1':
			node.print_information()
		elif option == '2':
			initiate_put(node)
		elif option == '4':
			node.print_files()
		else:
			continue


def server_thread(this_node, conn):
	while True:
		msg = conn.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ARE_YOU_ALONE':
			if (this_node.successor == this_node.port) and (this_node.predecessor == this_node.port):
				conn.send('YES'.encode('utf-8'))
			else:
				conn.send('NO'.encode('utf-8'))
				continue

		if msg == 'UPDATE_SUCCESSOR_AND_PREDECESSOR':
			conn.send('ACK'.encode('utf-8'))
			other_port = (conn.recv(BUFFER_SIZE)).decode('utf-8')
			this_node.predecessor = other_port
			this_node.successor = other_port

		if msg == 'I_AM_YOUR_PREDECESSOR':
			conn.send('ACK'.encode('utf-8'))
			port = int(conn.recv(BUFFER_SIZE).decode('utf-8'))
			this_node.predecessor = port

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
			conn.send(str(this_node.predecessor).encode('utf-8'))

		if msg == 'UPDATE_SECOND_SUCCESSOR':
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((IP_ADDRESS, int(this_node.successor)))
			s.send('SEND_ME_SUCCESSOR'.encode('utf-8'))
			this_node.second_successor = int(s.recv(BUFFER_SIZE).decode('utf-8'))
			s.close()

		if msg == 'PREDECESSOR_LEAVING':
			conn.send('ACK'.encode('utf-8'))
			leaving_port = int(conn.recv(BUFFER_SIZE).decode('utf-8'))
			conn.send('ACK'.encode('utf-8'))
			new_pred = int(conn.recv(BUFFER_SIZE).decode('utf-8'))
			this_node.predecessor = new_pred
			if leaving_port == this_node.second_successor:
				this_node.second_successor = this_node.port

		if msg == 'SUCCESSOR_LEAVING':
			conn.send('ACK'.encode('utf-8'))
			new_succ = int(conn.recv(BUFFER_SIZE).decode('utf-8'))
			this_node.successor = new_succ
			conn.send('ACK'.encode('utf-8'))
			new_second_succ = int(conn.recv(BUFFER_SIZE).decode('utf-8'))
			this_node.second_successor = new_second_succ

			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((IP_ADDRESS, int(this_node.predecessor)))
			s.send('UPDATE_SECOND_SUCCESSOR_ALONE'.encode('utf-8'))
			s.close()

		if msg == 'UPDATE_SECOND_SUCCESSOR_ALONE':
			update_second_seccessor_alone(this_node)

		if msg == 'SUCCESSOR_AND_PREDECESSOR_LEAVING':
			this_node.successor = this_node.port
			this_node.predecessor = this_node.port
			this_node.second_successor = this_node.port
			conn.send('ACK'.encode('utf-8'))

		if msg == 'RECEIVE_FILE':
			conn.send('ACK'.encode('utf-8'))
			file_name = conn.recv(BUFFER_SIZE).decode('utf-8')
			conn.send('ACK'.encode('utf-8'))
			file_size = float(conn.recv(BUFFER_SIZE).decode('utf-8'))
			conn.send('ACK'.encode('utf-8'))

			file = open(file_name,'wb')
			to_write = conn.recv(BUFFER_SIZE)
			file.write(to_write)
			received = len(to_write)
			while received < file_size:
				to_write = conn.recv(BUFFER_SIZE)
				received += len(to_write)
				file.write(to_write)
			file.close()
			this_node.file_list.append(file_name)
			msg = conn.recv(BUFFER_SIZE).decode('utf-8')
			if msg == 'FINISHED_SENDING':
				conn.send('File saved'.encode('utf-8'))	


def update_second_seccessor_alone(node):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(node.successor)))
	s.send('SEND_ME_SUCCESSOR'.encode('utf-8'))
	new_second_succ = int(s.recv(BUFFER_SIZE).decode('utf-8'))
	s.close()
	node.second_successor = new_second_succ


def update_second_seccessor(node):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(node.predecessor)))
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
	if (str(port) == other_port) or (int(port) > 65535) or (int(port) < 0):
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
