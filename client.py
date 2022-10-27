import socket
import threading
import pickle
from datetime import time
from enum import Enum
import tqdm  # for progress bar
import os
import time

host = '192.168.1.184'
port = 60001


class MCP_Message_Codes(Enum):
    Invalid_Message = 0
    User_Message = 1
    File_Message_SEND = 2
    File_Message_RECV = 3
    File_Message_ACK = 4
    File_Message_SEND_ACK = 5
    Login_Message = 8
    Disconnect_Message = 9


class MCP_Message:
    def __init__(self, code=MCP_Message_Codes.Invalid_Message, sender="", receiver="", message=""):
        self.code = code
        self.sender = sender
        self.receiver = receiver
        self.message = message


class MCP_File:
    def __init__(self, filename="", filesize=0, type="", sender="", receiver="", message=""):
        self.filename = filename
        self.filesize = filesize
        self.type = type
        self.sender = sender
        self.receiver = receiver
        self.message = message


def CustomFileSender(client, username, filename, filesize, user_to_send_to):
    file_socket = socket.socket()
    connect_try_count = 3
    while connect_try_count:
        try:
            file_socket.connect((host, port))
            break
        except TimeoutError as e:
            connect_try_count = connect_try_count - 1
        except ConnectionError as e:
            connect_try_count = connect_try_count - 1

    if connect_try_count:
        filename = filename[0]
        file_socket.send(pickle.dumps(
            MCP_Message(code=MCP_Message_Codes.File_Message_SEND_ACK, message=filename + "|" + filesize,
                        sender=username, receiver=user_to_send_to)))

        progress_bar = tqdm.tqdm(range(int(filesize)), f"Sending {filename}", unit="B", unit_scale=True,
                                 unit_divisor=1000, miniters=1)
        with open(filename, "rb") as fstream:
            while True:
                bytes_read = fstream.read(1024)
                if not bytes_read:
                    break  # eof
                file_socket.sendall(bytes_read)
                time.sleep(0.01)
                progress_bar.update(len(bytes_read))

        print("File sent successfully")

        received_message = pickle.loads(client.recv(1024))
        print(received_message.message)
        while True:
            time.sleep(1)  # until server shuts down
            print("Waiting for server to finish sending and shut me down")
    else:
        print(f"Couldn't connect file sending socket from {client}. Aborting.")


def CustomSender(username, client):
    client.send(pickle.dumps(MCP_Message(code=MCP_Message_Codes.Login_Message, message=username)))
    connected_message = pickle.loads(client.recv(1024))
    print(connected_message.message)

    threading.Thread(target=CustomListener, args=(client, username,)).start()
    while True:
        cmd = input(">> ")
        cmd_arr = cmd.split(" ")
        if cmd_arr[0] == "exit":  # exit
            message = MCP_Message(code=MCP_Message_Codes.Disconnect_Message)
            client.send(pickle.dumps(message))
            break
        elif cmd_arr[0] == "msg":  # msg user123 hello there
            user_to_send_to = cmd_arr[1]
            message = " ".join(cmd_arr[2:])
            to_send = MCP_Message(code=MCP_Message_Codes.User_Message, receiver=user_to_send_to, message=message)
            client.send(pickle.dumps(to_send))
        elif cmd_arr[0] == "send":  # send user123 data.csv
            user_to_send_to = cmd_arr[1]
            filename = " ".join(cmd_arr[2:])
            try:
                filesize = os.path.getsize(filename)
            except FileNotFoundError as fnfe:
                print("File does not exist on machine. Error:{fnfe}")

            message = filename + "|" + str(filesize)
            to_send = MCP_Message(code=MCP_Message_Codes.File_Message_SEND, receiver=user_to_send_to, sender=username,
                                  message=message)
            client.send(pickle.dumps(to_send))  # send request to server to send data

        else:
            continue


def CustomFileListener(client, username, user_receiving_from, message):
    # create new socket for receving the file
    file_socket = socket.socket()
    connect_try_count = 3
    while connect_try_count:
        try:
            file_socket.connect((host, port))
            break
        except TimeoutError as e:
            connect_try_count = connect_try_count - 1
        except ConnectionError as e:
            connect_try_count = connect_try_count - 1

    if connect_try_count:
        file_message = message.split("|")
        file_name = file_message[0]
        file_name = os.path.basename(file_name)
        file_size = int(file_message[1])

        to_send = MCP_Message(code=MCP_Message_Codes.File_Message_ACK, sender=username, message=message)
        file_socket.send(pickle.dumps(to_send))  # send request to server to receive data

        amountread = 0
        progress_bar = tqdm.tqdm(range(file_size), f"Receiving {file_name}", unit="B", unit_scale=True,
                                 unit_divisor=1000, miniters=1)
        with open(file_name, "wb") as f:
            while True:
                bytes_read = file_socket.recv(1024)
                amountread += 1024
                if not bytes_read:
                    break
                f.write(bytes_read)
                progress_bar.update(len(bytes_read))
                time.sleep(0.01)
                if amountread > file_size:
                    break

        print(f"File {file_name} received from {user_receiving_from} successfully")
        file_socket.shutdown(socket.SHUT_RDWR)

    else:
        print(f"Couldn't connect file receiving socket in {client}. Aborting.")


# receive the file

def CustomListener(client, username):
    while True:
        try:
            received_message = pickle.loads(client.recv(1024))
            if received_message.code == MCP_Message_Codes.User_Message:
                print(f"{received_message.sender}:{received_message.message}")
            elif received_message.code == MCP_Message_Codes.Disconnect_Message:
                print("Disconnected from the server")
                if received_message.message != "":
                    print(f"Reason: {received_message.message}")
                break
            elif received_message.code == MCP_Message_Codes.Invalid_Message:
                print(received_message.message)
            elif received_message.code == MCP_Message_Codes.File_Message_ACK:  # start sending to server
                file_message = received_message.message.split("|")
                filename = file_message[:-1]
                filesize = file_message[-1]
                user_to_send_to = received_message.receiver
                threading.Thread(target=CustomFileSender,
                                 args=(client, username, filename, filesize, user_to_send_to)).start()
            elif received_message.code == MCP_Message_Codes.File_Message_SEND:
                print("Received request from server to send file. Sending to server that I accept the send\n")
                user_receiving_from = received_message.sender
                threading.Thread(target=CustomFileListener,
                                 args=(client, username, user_receiving_from, received_message.message)).start()
        except Exception as e:
            print(f"Warning! Exception caught: {e}")


def main():
    print("\texit:                      exits")
    print("\tmsg [user] [message]       sends message to user")
    print("\tsend [user] [file.csv]     sends file to user")
    username = input("Enter username: ")
    client = socket.socket()
    connect_try_count = 3
    while connect_try_count:
        try:
            client.connect((host, port))
            break
        except TimeoutError as e:
            connect_try_count = connect_try_count - 1
            print(f'{e}. {connect_try_count} tries left.')
        except ConnectionError as e:
            connect_try_count = connect_try_count - 1
            print(f'{e}. {connect_try_count} tries left.')

    if connect_try_count:
        threading.Thread(target=CustomSender, args=(username, client,)).start()
    else:
        print("Couldn't connect. Aborting.")


if __name__ == '__main__':
    main()
