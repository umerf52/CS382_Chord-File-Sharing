import socket
import threading
import hashlib
import argparse
import os
import time

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
		# Tell the other node to update its successor and predecessor
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

		# Wrapping around the DHT ring
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
	# Inform successor
	s.send('I_AM_YOUR_PREDECESSOR'.encode('utf-8'))
	msg = s.recv(BUFFER_SIZE).decode('utf-8')
	if msg == 'ACK':
		s.send(str(node.port).encode('utf-8'))
		node.successor = known_port
	s.close()

	# Inform predecessor
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
	# Only 1 node in DHT
	if (node.successor == node.port) and (node.predecessor == node.port):
		return

	# 2 nodes in DHT
	elif node.successor == node.predecessor:
		for file in node.file_list:
			send_file(file, node.successor)
		another_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		another_socket.connect((IP_ADDRESS, int(node.successor)))
		another_socket.send('SUCCESSOR_AND_PREDECESSOR_LEAVING'.encode('utf-8'))
		msg = another_socket.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ACK':
			pass
		another_socket.close()
		return

	# More than 2 nodes in DHT
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
		for file in node.file_list:
			send_file(file, node.successor)
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


# Similar to send_file() other than the fact it does not replicate the file
# This separate function is needed because when I used send_file() for replication
# as well, file will not be replicated instead sockets will get stuck in limbo
# I don't know why
def replicate_file(file_name, port):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(port)))

	s.send('REPLICATE_FILE'.encode('utf-8'))
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
				# A do-while loop
				to_send = file.read(BUFFER_SIZE)
				sent = len(to_send)
				s.send(to_send)
				while sent < file_size:
					to_send = file.read(BUFFER_SIZE)
					s.send(to_send)
					sent += len(to_send)
				file.close()

		elif msg == 'ALREADY_HAVE_IT':
			pass
	s.close()


def send_file(file_name, port):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(port)))

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
				# A do-while loop
				to_send = file.read(BUFFER_SIZE)
				sent = len(to_send)
				s.send(to_send)
				while sent < file_size:
					to_send = file.read(BUFFER_SIZE)
					s.send(to_send)
					sent += len(to_send)
				file.close()

		elif msg == 'ALREADY_HAVE_IT':
			pass
	s.close()


def initiate_put(node):
	file_name = input('Enter the name of the file you want to "put": ')
	print(' ')

	if os.path.isfile(file_name):
		file_key = hash_func(file_name)
		pred_key = hash_func(IP_ADDRESS + str(node.predecessor))
		if (node.port == node.successor) and (node.port == node.predecessor):
			if file_name not in node.file_list:
				node.file_list.append(file_name)
			print('File saved\n')

		# Similar logic to join_me()	
		elif ((file_key < node.key) and ((file_key > pred_key and node.key > pred_key) or (file_key < pred_key and node.key < pred_key))) or (file_key > node.key and pred_key > node.key and file_key > pred_key):
			if file_name not in node.file_list:
				node.file_list.append(file_name)
			print('File saved\n')
			t = threading.Thread(target=replicate_file, args=(file_name, node.successor))
			t.daemon = True
			t.start()

		else:
			t = threading.Thread(target=put_iterative, args=(file_key, file_name, node.successor))
			t.daemon = True
			t.start()
	else:
		print('File does not exist\n')


def put_iterative(file_key, file_name, new_port):
	temp_key = hash_func(IP_ADDRESS + str(new_port))
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(new_port)))
	s.send('SEND_ME_PREDECESSOR'.encode('utf-8'))
	pred_port = int(s.recv(BUFFER_SIZE).decode('utf-8'))
	pred_key = hash_func(IP_ADDRESS + str(pred_port))

	# Check if file should be placed at this node or sent forward
	if ((file_key < temp_key) and ((file_key > pred_key and temp_key > pred_key) or (file_key < pred_key and temp_key < pred_key))) or (file_key > temp_key and pred_key > temp_key and file_key > pred_key):
		s.close()
		send_file(file_name, new_port)
		print('Finsihed sending file\n')

	else:
		s.send('SEND_ME_SUCCESSOR'.encode('utf-8'))
		new_succ = int(s.recv(BUFFER_SIZE).decode('utf-8'))
		s.close()
		put_iterative(file_key, file_name, new_succ)


def initiate_get(node):
	file_name = input('Enter the name of the file you want to "get": ')
	print(' ')
	if file_name != '':
		if file_name in node.file_list:
			print('File already exists\n')
			return

		else:
			# If there is no other node than me, file does not exist
			if (node.port == node.successor) and (node.port == node.successor):
				print('File not found\n')
				return

			file_key = hash_func(file_name)
			t = threading.Thread(target=get_iterative, args=(file_key, node.successor, file_name, node))
			t.daemon = True
			t.start()
	else:
		print('Invalid file name\n')


def get_iterative(file_key, port, file_name, node):
	temp_key = hash_func(IP_ADDRESS + str(port))
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(port)))
	s.send('SEND_ME_PREDECESSOR'.encode('utf-8'))
	pred_port = int(s.recv(BUFFER_SIZE).decode('utf-8'))
	pred_key = hash_func(IP_ADDRESS+str(pred_port))
	s.send('SEND_ME_SUCCESSOR'.encode('utf-8'))
	new_succ = int(s.recv(BUFFER_SIZE).decode('utf-8'))

	# Check if file should exist on this node
	if ((file_key < temp_key) and ((file_key > pred_key and temp_key > pred_key) or (file_key < pred_key and temp_key < pred_key))) or (file_key > temp_key and pred_key > temp_key and file_key > pred_key):
		s.send(('DO_YOU_HAVE_FILE').encode('utf-8'))
		msg = s.recv(BUFFER_SIZE).decode('utf-8')
		if msg == 'ACK':
			msg = ''
			s.send(file_name.encode('utf-8'))
			msg = s.recv(BUFFER_SIZE).decode('utf-8')
			if msg == 'YES':
				get_file_actual(port, file_name, node)

			# Ask if successor of this node has file
			# File replication strategy is that successor should also maintain
			# a copy of file
			else:
				if pred_port == new_succ:	
					print('File not found\n')
					return
				msg = ''
				another_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				another_socket.connect((IP_ADDRESS, int(new_succ)))
				another_socket.send('DO_YOU_HAVE_FILE'.encode('utf-8'))
				msg = another_socket.recv(BUFFER_SIZE).decode('utf-8')
				if msg == 'ACK':
					msg = ''
					another_socket.send(file_name.encode('utf-8'))	
					msg = another_socket.recv(BUFFER_SIZE).decode('utf-8')
					another_socket.close()
					if msg == 'YES':
						get_file_actual(new_succ, file_name, node)

					else:
						print('File not found\n')

	else:
		s.close()
		get_iterative(file_key, new_succ, file_name, node)


def get_file_actual(port, file_name, node):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(port)))
	s.send('SEND_FILE'.encode('utf-8'))
	msg = s.recv(BUFFER_SIZE).decode('utf-8')
	if msg == 'ACK':
		s.send(file_name.encode('utf-8'))
		file_size = float(s.recv(BUFFER_SIZE).decode('utf-8'))
		s.send('ACK'.encode('utf-8'))

		file = open(file_name,'wb')
		# A do-while loop
		to_write = s.recv(BUFFER_SIZE)
		file.write(to_write)
		received = len(to_write)
		while received < file_size:
			to_write = s.recv(BUFFER_SIZE)
			received += len(to_write)
			file.write(to_write)
		file.close()
		if file_name not in node.file_list:
			node.file_list.append(file_name)
		print('File received\n')


def client_thread(node):
	while True:
		option = input('Enter 0 to leave DHT\nEnter 1 to print links\nEnter 2 to "put" a file\nEnter 3 to "get" a file\nEnter 4 to print available files\n\n')
		if option == '0':
			node_leaving(node)
			os._exit(0)
		elif option == '1':
			node.print_information()
		elif option == '2':
			initiate_put(node)
		elif option == '3':
			initiate_get(node)
		elif option == '4':
			node.print_files()
		else:
			continue


def server_thread(this_node, conn):
	while True:
		try:
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
				# Edge case for 2nd successor
				if leaving_port == this_node.second_successor:
					this_node.second_successor = this_node.port

			if msg == 'SUCCESSOR_LEAVING':
				conn.send('ACK'.encode('utf-8'))
				new_succ = int(conn.recv(BUFFER_SIZE).decode('utf-8'))
				this_node.successor = new_succ
				conn.send('ACK'.encode('utf-8'))
				# Update 2nd sucessor as well
				new_second_succ = int(conn.recv(BUFFER_SIZE).decode('utf-8'))
				this_node.second_successor = new_second_succ

				# Tell predecessor to update its 2nd successor
				s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				s.connect((IP_ADDRESS, int(this_node.predecessor)))
				s.send('UPDATE_SECOND_SUCCESSOR_ALONE'.encode('utf-8'))
				s.close()

			if msg == 'UPDATE_SECOND_SUCCESSOR_ALONE':
				update_second_seccessor_alone(this_node)
				if (int(this_node.successor) == int(this_node.predecessor)):
					for file in this_node.file_list:
						send_file(file, this_node.successor)

			if msg == 'SUCCESSOR_AND_PREDECESSOR_LEAVING':
				this_node.successor = this_node.port
				this_node.predecessor = this_node.port
				this_node.second_successor = this_node.port
				conn.send('ACK'.encode('utf-8'))

			if msg == 'RECEIVE_FILE':
				conn.send('ACK'.encode('utf-8'))
				file_name = conn.recv(BUFFER_SIZE).decode('utf-8')
				if file_name in this_node.file_list:
					conn.send('ALREADY_HAVE_IT'.encode('utf-8'))
					replicate_file(file_name, this_node.successor)
					continue

				else:
					conn.send('ACK'.encode('utf-8'))
				file_size = float(conn.recv(BUFFER_SIZE).decode('utf-8'))
				conn.send('ACK'.encode('utf-8'))

				file = open(file_name,'wb')
				to_write = conn.recv(BUFFER_SIZE)
				# A do-while loop
				file.write(to_write)
				received = len(to_write)
				while received < file_size:
					to_write = conn.recv(BUFFER_SIZE)
					received += len(to_write)
					file.write(to_write)
				file.close()
				if file_name not in this_node.file_list:
					this_node.file_list.append(file_name)

				replicate_file(file_name, this_node.successor)

			if msg == 'REPLICATE_FILE':
				conn.send('ACK'.encode('utf-8'))
				file_name = conn.recv(BUFFER_SIZE).decode('utf-8')	
				if file_name in this_node.file_list:
					conn.send('ALREADY_HAVE_IT'.encode('utf-8'))
					continue
				else:
					conn.send('ACK'.encode('utf-8'))
				file_size = float(conn.recv(BUFFER_SIZE).decode('utf-8'))
				conn.send('ACK'.encode('utf-8'))

				file = open(file_name,'wb')
				to_write = conn.recv(BUFFER_SIZE)
				# A do-while loop
				file.write(to_write)
				received = len(to_write)
				while received < file_size:
					to_write = conn.recv(BUFFER_SIZE)
					received += len(to_write)
					file.write(to_write)
				file.close()
				if file_name not in this_node.file_list:
					this_node.file_list.append(file_name)

			if msg == 'DO_YOU_HAVE_FILE':
				conn.send('ACK'.encode('utf-8'))
				file_name = conn.recv(BUFFER_SIZE).decode('utf-8')
				if file_name in this_node.file_list:
					conn.send('YES'.encode('utf-8'))
				else:
					conn.send('NO'.encode('utf-8'))

			if msg == 'SEND_FILE':
				conn.send('ACK'.encode('utf-8'))
				file_name = conn.recv(BUFFER_SIZE).decode('utf-8')
				if os.path.isfile(file_name):
					file_size = os.path.getsize(file_name) 
					conn.send(str(file_size).encode('utf-8'))
					msg = conn.recv(BUFFER_SIZE).decode('utf-8')
					if msg == 'ACK':
						file = open(file_name, 'rb')
						to_send = file.read(BUFFER_SIZE)
						# A do-while loop
						sent = len(to_send)
						conn.send(to_send)
						while sent < file_size:
							to_send = file.read(BUFFER_SIZE)
							conn.send(to_send)
							sent += len(to_send)
						file.close()

				else:
					print('Error, file does not exist\n')


		except:
			print('A connection was forcibly closed\n')
			conn.close()
			break


def update_second_seccessor_alone(node):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(node.successor)))
	s.send('SEND_ME_SUCCESSOR'.encode('utf-8'))
	new_second_succ = int(s.recv(BUFFER_SIZE).decode('utf-8'))
	s.close()
	node.second_successor = new_second_succ


# Tell predecessor of predecssor to update its second sucessor
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


# Check if successor has not left unexpectedly
def ping_successor(node):
	failed_attempts = 0
	while True:
		if (node.port == node.successor) and (node.port == node.predecessor):
			pass
		else:
			try:
				s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				s.connect((IP_ADDRESS, int(node.successor)))
				s.close()
				failed_attempts = 0
			except:
				failed_attempts = failed_attempts + 1
				if failed_attempts == 3:
					successor_left_unexpectedly(node)
					failed_attempts = 0

		time.sleep(10)


def successor_left_unexpectedly(node):
	node.successor = node.second_successor
	update_second_seccessor_alone(node)
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((IP_ADDRESS, int(node.successor)))
	s.send('I_AM_YOUR_PREDECESSOR'.encode('utf-8'))
	msg = s.recv(BUFFER_SIZE).decode('utf-8')
	if msg == 'ACK':
		s.send(str(node.port).encode('utf-8'))
	s.close

	for file in node.file_list:
		send_file(file, node.successor)

	another_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	another_socket.connect((IP_ADDRESS, int(node.predecessor)))
	another_socket.send('UPDATE_SECOND_SUCCESSOR_ALONE'.encode('utf-8'))
	another_socket.close()


def main():
	parser = argparse.ArgumentParser(description='Join DHT. ')
	parser.add_argument('port', type=int, nargs=1)
	args = parser.parse_args()

	port = args.port[0]
	node = Node(port)
	t = threading.Thread(target=ping_successor, args=(node,))
	t.daemon = True
	t.start()
	print('My key is:', node.key)

	other_port = input('Enter port of any known node, leave blank otherwise: ')
	if (str(port) == other_port) or (int(port) > 65535) or (int(port) < 0):
		print('Invalid ports\n')
		return
	if other_port:
		join_me(node, other_port)
		set_second_successor(node)
		# Tell predecessor of predecssor to update its second sucessor
		update_second_seccessor(node)

	# Thread for client-side operations such as get, put, etc
	t = threading.Thread(target=client_thread, args=(node,))
	t.daemon = True
	t.start()

	# Thread to accept incoming connections from other nodes
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
