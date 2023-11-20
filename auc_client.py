# Pinxiang Wang 2023/10/18 -- Part 1

# Pinxiang Wang pwang25 2023/11/20  -- Part 2
# Mengzhe Wang mwang39 2023/11/20   -- Part 2

import os
import struct
import sys
import threading
import time
import random
from socket import socket, AF_INET, SOCK_STREAM, SOCK_DGRAM
import re

chunk_size = 2000
TIMEOUT = 5
HOST = '127.0.0.1'
PORT = 5001
CLIENT_PORT = -1

# Test Seller Msg:
# 1 100 10 apple
bid_received = False
bid_end = False
is_winner = False

WINNER_IP = '-'
SELLER_IP = '-'

# ip regex:
ip_regex = re.compile(
    r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$')

PACKET_LOSS = 0


def client(address, port, client_port, packet_loss_rate):
    global CLIENT_PORT, PACKET_LOSS
    CLIENT_PORT = client_port
    PACKET_LOSS = packet_loss_rate
    try:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect((address, port))
        content = sock.recv(1024)

        if content == b'Your role is [Seller]!':
            print(content.decode())
            seller_handler(sock)
        elif content == b'Your role is [Buyer]!':
            print(content.decode())
            buyer_handler(sock)
        elif content == b'Connection rejected!':
            print('Server is busy, please try again later.')
            sock.close()
    except Exception as e:
        print('Errors happened on client side:', e)
        sock.close()


def buyer_handler(sock):
    global bid_received, is_winner, SELLER_IP
    # client_msg = 'buyer is online'
    response_msg = sock.recv(1024)
    if response_msg == b'Bidding starts!':
        while True:
            if not bid_received:
                keyboard_input = input('Please submit your bid:')
                sock.send(keyboard_input.encode())

            response_msg = sock.recv(1024)  # receive the bid result
            if response_msg == b'Bid received!':
                bid_received = True

                print('Bid received. Please wait...')
            if response_msg == b'':
                return
            elif response_msg == b'Invalid auction request!':
                print('Invalid bid, please submit a positive integer!')
                continue
            # elif response_msg.decode().startswith('Auction finished!'):
            #     # sock.send(b'Result received!')
            #     continue
            pattern = re.compile(r'\bYou won\b')
            match = re.search(pattern, response_msg.decode())
            if match:
                is_winner = True
            if response_msg.decode().endswith('Bid round ends!') and not is_winner:
                print(response_msg.decode())
                print('Disconnecting from the Auctioneer server. Auction is over!')
                sock.close()
                break

            else:
                print(response_msg.decode())

                if is_winner:
                    print('Project2:' + response_msg.decode() + '\n')
                    print('-----------------')
                    content = response_msg.decode().split(' ')
                    for item in content:
                        # item match ip regex:
                        if ip_regex.match(item):
                            SELLER_IP = item
                    print('seller ip:', SELLER_IP)
                    if SELLER_IP != '-':
                        # winning_buyer_udp_rdt_receiver(seller_ip)
                        rdt_file_receiver(SELLER_IP, 'received.file')
                    # sock.send(b'Result received!')
        # if is_winner:
        #     winning_buyer_udp_rdt_receiver(seller_ip)


def seller_handler(sock):
    global bid_end, WINNER_IP, SELLER_IP
    while not bid_end:
        client_msg = input("Please submit auction request:")
        sock.send(client_msg.encode())
        response_msg = sock.recv(1024)

        if response_msg == b'Invalid Auction Request!':
            print(response_msg.decode())
            continue
        elif response_msg == b'Auction start':
            print(response_msg.decode())
            while True:
                response_msg = sock.recv(1024)
                # print(response_msg)
                # seller receives msg from server to get the winner IP
                if response_msg == b'':
                    continue
                else:
                    print(response_msg.decode())
                    if response_msg.decode().startswith('_Auction finished!'):
                        print('Project2:' + response_msg.decode() + '\n')
                        content = response_msg.decode().split(' ')
                        # print(content)
                        for item in content:
                            # item match ip regex:
                            if ip_regex.match(item):
                                WINNER_IP = item
                        print('winner ip:', WINNER_IP)
                        if WINNER_IP != '-':
                            rdt_file_sender('tosend.file')
                        # sock.send(b'Result received!')
                        # winner buyer receives msg from server to get the seller IP

                # if response_msg == 'All buyers connected!':
                #     break


def rdt_file_sender(file_path):
    # Create the UDP socket
    global chunk_size, PACKET_LOSS, WINNER_IP, CLIENT_PORT
    seller_socket = socket(AF_INET, SOCK_DGRAM)
    print('UDP socket opened for RDT')
    with open(file_path, 'rb') as file:
        content = file.read()
    file_size = len(content)
    # Split the file content into chunks
    chunks = [content[i:i + chunk_size] for i in range(0, file_size, chunk_size)]
    seq = 1  # Sequence number starts at 0
    # Send the total file size to the buyer
    start_msg = f"{file_size}"
    type_num = 3
    # first control msg: sending the total file size to the seller.
    start_message = type_num.to_bytes(1, 'big') + start_msg.encode()
    seller_socket.sendto(start_message, (WINNER_IP, CLIENT_PORT))
    print(f"Sending control seq {0}: start  {start_msg}")

    # Wait for ACK of the start message, then start sending data
    while True:
        try:
            # Set timeout to 2 seconds
            seller_socket.settimeout(2)  # Wait for up to 2 seconds for an ACK
            # Receive ACK
            ack, addr = seller_socket.recvfrom(1024)
            if ack == b'0':
                print("ACK received: ", ack.decode())
                break # Start sending data if ACK is received
        except Exception as e:
            print('error:', e)
            # Resend the start message if no ACK is received within the timeout period
            print(f"Msg re-sent: ", ack.decode())
            seller_socket.sendto(start_message, (WINNER_IP, CLIENT_PORT))
    # Send the data
    current_size = 0
    # print(f"Sending data seq {seq}: {current_size} / {file_size}")
    for chunk in chunks:
        current_size = current_size + len(chunk)
        # Send the chunk with a sequence number
        # print(f"Sending data seq {seq}: {current_size} / {file_size}")
        message = seq.to_bytes(1, 'big') + chunk
        print(f"Sending data seq {seq}: {current_size} / {file_size}")
        if random.random() > packet_loss:
            # Send the message if it's not dropped
            seller_socket.sendto(message, (WINNER_IP, CLIENT_PORT))
        else:
            print(f"Ack dropped: {seq}")

        while True:
            try:
                # Set timeout to 2 seconds
                seller_socket.settimeout(2)
                # Receive ACK
                ack, _ = seller_socket.recvfrom(1024)
                ack = int.from_bytes(ack, 'big')

                if ack == seq:
                    print(f"ACK received: {ack}")
                    seq = (seq + 1) % 2  # Flip the sequence number
                    break
                    # Send the next chunk if ACK is received
            except Exception as e:
                print('error:', e)
                print(f"Msg re-sent: {seq}")
                if random.random() < packet_loss:
                    print(f"Ack dropped: {seq}")
                else:
                    seller_socket.sendto(message, (WINNER_IP, CLIENT_PORT))

    fin_msg = b'fin'
    # Send the finish message
    seller_socket.sendto(fin_msg,(WINNER_IP, CLIENT_PORT))
    print(f"Sending control seq {seq}: {'fin'}")

    # Wait for ACK of the finish message, then close the socket
    while True:
        try:
            seller_socket.settimeout(2)
            ack, _ = seller_socket.recvfrom(1024)
            ack = int.from_bytes(ack, 'big')
            if ack == seq:
                print(f"ACK received: {ack}")
                break
        except Exception as e:
            print('error:', e)
            # Resend the finish message if no ACK is received within the timeout period
            print(f"Msg re-sent: {ack}")
            seller_socket.sendto(fin_msg, (WINNER_IP, CLIENT_PORT))

    seller_socket.close()
    print("File transfer completed and socket closed.")


def rdt_file_receiver(expected_seller_ip, file_path):
    global  SELLER_IP, CLIENT_PORT, PACKET_LOSS
    # Create the UDP socket
    client_socket = socket(AF_INET, SOCK_DGRAM)
    client_socket.bind(('', CLIENT_PORT))
    # Open the file to write received data
    with open(file_path, 'wb') as file:
        sequence_number = 1  # Expected sequence number
        size = 0
        current_size = 0
        start_time = 0
        print(f"Start receving file.")
        while True:
            # Set timeout to 2 seconds
            if random.random() < packet_loss:
                print(f"Pkt dropped: {sequence_number}")
                continue
            # Receive the data
            data_packet, address = client_socket.recvfrom(2048)
            sender_ip = address[0]
            seq = data_packet[0]

            # Authentication of the message based on the negotiated IP address
            if sender_ip != expected_seller_ip:
                continue  # Ignore the packet if it's from an unexpected IP address

            # Handle control message
            if b'fin' in data_packet:
                print("All data received! Exiting...")
                client_socket.sendto(sequence_number.to_bytes(1, 'big'), address)  # Acknowledge the finish message
                finished_time = time.time()
                print(f"Total size: {size} bytes , Transmission Time (TCT) {(finished_time - start_time)} seconds, "
                      f"Average Throughput(AT) {size / (finished_time - start_time)} bps")
                break
            # Handle start message
            if seq == 3:
                # Set the start time
                start_time = time.time()
                # Get the file size from the start message
                file_size = data_packet[1:].decode()
                size = int(file_size)
                # Send ACK
                print(f"Msg received: {0}")
                print(f"Ack sent: {0}")  # Acknowledge the start message

                if random.random() < packet_loss:
                    print(f"Pkt dropped: {0}")
                else:
                    client_socket.sendto(b'0', address)
                continue
            # Handle data message
            if seq == sequence_number:
                print(f"Msg received: {seq}")
                file.write(data_packet[1:])  # Write data excluding the sequence number
                print(f"Ack sent: {seq}")
                if random.random() < packet_loss:
                    print(f"Pkt dropped: {seq}")
                else:
                    client_socket.sendto(seq.to_bytes(1, 'big'), address)  # Send ACK
                current_size = current_size + len(data_packet[1:])
                print(f"Received data seq {seq}: {current_size} / {size}")
                sequence_number = (sequence_number+1)%2  # Flip the expected sequence number for Stop-and-Wait
            # Handle retransmission
            else:
                print(f"Msg receive with mismatched sequence number {seq}. Expecting {sequence_number}")
                client_socket.sendto(((sequence_number+1)%2).to_bytes(1, 'big'), address)  # Send ACK
                print(f"Ack re-sent: {((sequence_number+1)%2)}")
    # Close the socket
    client_socket.close()
    print(f"File successfully received and saved to {file_path}.")


if __name__ == "__main__":
    args = sys.argv
    HOST = args[1]
    PORT = int(args[2])
    ClINET_PORT = int(args[3])
    packet_loss = float(args[4])
    client(HOST, PORT, ClINET_PORT, packet_loss)
