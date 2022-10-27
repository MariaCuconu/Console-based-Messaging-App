import os
import socket
import threading
from enum import Enum
import pickle
import time

host = ''
port = 60001

connection_counter = 10
online_users = {}


class MCP_Message_Codes(Enum):
    Invalid_Message = 0
    User_Message = 1
    File_Message_SEND = 2
    File_Message_RECV = 3
    File_Message_ACK = 4
    File_Message_SEND_ACK = 5
    Login_Message = 8
    Disconnect_Message = 9


class MCP_File_Codes(Enum):
    Corrupt_File = 0
    Other_File = 1
    JPG_File = 2
    Text_File = 3


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


def CustomConnectionHandler(client_socket, client_address):
    global connection_counter
    print(f"New connection from {client_address}")
    try:
        received_message = pickle.loads(client_socket.recv(1024))
        if received_message.code == MCP_Message_Codes.Login_Message:
            username = received_message.message
            if username in online_users.keys():
                client_socket.send(
                    pickle.dumps(
                        MCP_Message(code=MCP_Message_Codes.Disconnect_Message, message="Username already taken")))
                client_socket.shutdown(socket.SHUT_RDWR)
                connection_counter += 1
            else:
                online_users[username] = client_socket
                print(f"User {username} connected")
                client_socket.send(
                    pickle.dumps(MCP_Message(code=MCP_Message_Codes.Login_Message, message=f"Hello {username}")))
        elif received_message.code == MCP_Message_Codes.File_Message_SEND_ACK:
            "filename|filesize"
            file_socket = client_socket
            file_message = received_message.message.split("|")
            filename = file_message[0]
            filename = os.path.basename(filename)
            filesize = int(file_message[1])
            amountread = 0
            with open(filename, "wb") as f:
                while True:
                    time.sleep(0.01)
                    bytes_read = file_socket.recv(1024)
                    amountread += 1024
                    if not bytes_read:
                        break
                    f.write(bytes_read)
                    if amountread > filesize:
                        break

            username = received_message.sender
            user_to_send_to = received_message.receiver
            print(f"Received file {filename} from user {username}. Sending it to {user_to_send_to}")
            file_socket.shutdown(socket.SHUT_RDWR)
            connection_counter += 1

            to_send = MCP_Message(code=MCP_Message_Codes.File_Message_SEND, sender=username, receiver=user_to_send_to,
                                  message=received_message.message)
            online_users[user_to_send_to].send(pickle.dumps(to_send))
            exit()

        elif received_message.code == MCP_Message_Codes.File_Message_ACK:
            # existing user wants to receive a file, start sending
            username = received_message.sender
            file_message = received_message.message.split("|")
            file_name = file_message[0]
            file_name = os.path.basename(file_name)
            file_socket = client_socket
            print(f"Sending file to {username}\n")
            with open(file_name, "rb") as fstream:
                while True:
                    bytes_read = fstream.read(1024)
                    if not bytes_read:
                        break  # eof
                    file_socket.sendall(bytes_read)
            print(f"Sent file to {username}\n")
            exit()


    except Exception as e:
        print(f"Error: {e}")
        return

    temp = MCP_Message()
    while True:
        try:
            received_message = pickle.loads(client_socket.recv(1024))
            if received_message.code == MCP_Message_Codes.Disconnect_Message:
                # when user disconnects remove it from connected users
                client_socket.send(
                    pickle.dumps(MCP_Message(code=MCP_Message_Codes.Disconnect_Message, message="Self disconnect")))
                client_socket.shutdown(socket.SHUT_RDWR)
                print(f"Client {username} disconnected")
                online_users.pop(username)
                connection_counter += 1
                break
            elif received_message.code == MCP_Message_Codes.User_Message:
                try:
                    user_to_send = received_message.receiver
                    message = received_message.message
                    to_send = MCP_Message(code=MCP_Message_Codes.User_Message, sender=username, message=message)
                    online_users[user_to_send].send(pickle.dumps(to_send))
                    print(f"User {username} sent message to {user_to_send}: {message}")
                except KeyError:
                    message = str(f"User {user_to_send} is not connected")
                    to_send = MCP_Message(code=MCP_Message_Codes.Invalid_Message, sender=username, message=message)
                    online_users[username].send(pickle.dumps(to_send))
                    print(f"User {username} tried to message {user_to_send}. {user_to_send} is not connected")

            elif received_message.code == MCP_Message_Codes.Invalid_Message:
                to_send = MCP_Message(code=MCP_Message_Codes.Invalid_Message, message="Invalid message")
                client_socket.send(pickle.dumps(to_send))
                print(f"Invalid message received from {username}")
            elif received_message.code == MCP_Message_Codes.File_Message_SEND:
                # existing user wants to send a file,waits confirmation from server
                username = received_message.sender
                user_to_send_to = received_message.receiver
                if user_to_send_to not in online_users.keys():
                    client_socket.send(pickle.dumps(MCP_Message(code=MCP_Message_Codes.Invalid_Message,
                                                                message=f"User to send to {user_to_send_to} is not connected\n")))
                    client_socket.shutdown(socket.SHUT_RDWR)
                    connection_counter += 1
                    exit()
                else:
                    client_socket.send(pickle.dumps(
                        MCP_Message(code=MCP_Message_Codes.File_Message_ACK, receiver=user_to_send_to, sender=username,
                                    message=received_message.message)))


        except Exception as e:
            print(f"Error:{e}")


def main():
    global connection_counter
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', port))
    server.listen(5)
    hostname = socket.gethostname()
    dns_resolved_addr = socket.gethostbyname(hostname)
    print(dns_resolved_addr)

    print("Waiting for connections")

    while True:
        if connection_counter:
            connection_counter -= 1
            client_socket, client_address = server.accept()
            threading.Thread(target=CustomConnectionHandler, args=(client_socket, client_address,)).start()


if __name__ == '__main__':
    print("Starting server")
    main()
