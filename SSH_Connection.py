import paramiko
import sys
import os
import json
import psycopg2
import time
import filecmp
import smtplib
import difflib
import socket
from datetime import datetime
from socket import gaierror


LOG_FOLDER = "D:/Remote_Logs_BelVPN/"
LOGS_TO_PARSE_FOLDER = 'D:/Remote_Logs_To_Parse/'


def rerun(func):
    def wrapper():
        while True:
            try:
                func()
                break
            except (KeyboardInterrupt, SystemExit):
                print('\nProcess interrupted and finished!')
                exit(0)
            except Exception as e:
                pass
    return wrapper


def get_my_local_ip():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    return local_ip


def send_email(subject, error, bodyText):
    try:
        with open("parameters.txt", "r") as file:
            data = json.loads(file.read())

        # Define the SMTP server credentials here:
        port = data['email']['port']
        smtp_server = data['email']['smtp_server']
        username = data['email']['username']
        password = data['email']['password']

        # specify the sender’s and receiver’s email addresses
        sender = data['email']['sender']
        receiver = data['email']['receiver']

        # type your message: use two newlines (\n) to separate the subject from the message body,
        # and use 'f' to  automatically insert variables in the text
        message = f"Subject: {subject} \n" \
                  f"To: {receiver} \n" \
                  f"From: {sender} \n" \
                  f"\n" \
                  f"Error : {error}\n\n" \
                  f"{bodyText}"

        # send your message with credentials specified above
        with smtplib.SMTP_SSL(smtp_server, port) as server:
            server.login(username, password)
            server.sendmail(sender, receiver, message.encode('utf8'))  # utf8 for correct display cyrillic
            server.quit()

        # tell the script to report if your message was sent or which errors need to be fixed
        now = datetime.now()
        dt_string = now.strftime("%d.%m.%Y %H:%M:%S")
        print(f'Email from {sender} to {receiver} sent on {dt_string} successfully')
    except (gaierror, ConnectionRefusedError):
        print('Failed to connect to the SMTP server. Bad connection settings')
    except smtplib.SMTPServerDisconnected:
        print('Failed to connect to the SMTP server. Wrong user/password')
    except smtplib.SMTPException as e:
        print('SMTP error occurred: ' + str(e))


def create_connection(ssh, server):
    now = datetime.now()
    dt_string = now.strftime("%d.%m.%Y %H:%M:%S")
    isEmailSend = False
    while True:
        try:
            #  READ PARAMETERS FROM JSON
            with open("parameters.txt", "r") as file:
                data = json.loads(file.read())
            ssh.connect(data[server]['ip'], data[server]['port'], data[server]['username'], data[server]['password'])
            if isEmailSend:
                now = datetime.now()
                dt_string = now.strftime("%d.%m.%Y %H:%M:%S")
                send_email(f'Script ({get_my_local_ip()}) successfully connected via SSH to Bel VPN Gate',
                           f'No errors found',
                           f'SSH to Bel VPN Gate is available again since last check = {dt_string}')
                isEmailSend = False
            break
        except (paramiko.ssh_exception.BadHostKeyException,
                paramiko.ssh_exception.AuthenticationException,
                paramiko.ssh_exception.SSHException,
                paramiko.ssh_exception.socket.error) as error:
            print(f'Error: {error}')
            print(f"Server not available from last check = {dt_string}")
            if not isEmailSend:
                send_email(f'Script ({get_my_local_ip()}) failed to connect via SSH to Bel VPN Gate',
                           error,
                           f'Bel VPN Gate is not available since last check = {dt_string}')
                isEmailSend = True
            print(f'Sleep for 1 minute')
            sleep_for(60)  # delay for 1 minute


def exec_ssh_command():
    #  COMMANDS TO EXECUTE OVER SSH
    # command = 'tail -n 10 /var/log/cspvpngate.log'
    # command = 'sa_mgr show -detail'
    command = 'sa_mgr show'

    #  RUNNING COMMANDS ON THE REMOTE MACHINE
    stdin, stdout, stderr = ssh.exec_command(command)

    #  OUTPUT OF EXECUTABLE COMMANDS
    outlines = stdout.readlines()
    resp = ''.join(outlines)
    print()
    print(resp)


@rerun
def get_remote_files():

    for fname in os.listdir(LOG_FOLDER):
        if fname.endswith('.log'):
            os.remove(f'{LOG_FOLDER}{fname}')

    for i in range(2, -1, -1):
        remote_path = f'/var/log/cspvpngate.log' if i == 0 else f'/var/log/cspvpngate.log.{i}'

        info = ftp_client.stat(remote_path)
        ftp_client.get(remote_path,
                       f'{LOG_FOLDER}'
                       f'{str(datetime.fromtimestamp(info.st_mtime)).replace(":", "-").replace(" ", "_")}_'
                       f'remote_log_{i}.log')

        time.sleep(1)


@rerun
def check_similar_files():
    files = os.listdir(LOG_FOLDER)

    # filecmp.cmp - COMPARE remote_log_2 WITH last remote_log_saved
    if not filecmp.cmp(f'{LOG_FOLDER}{files[-3]}',
                       f'{LOG_FOLDER}{files[-4]}'):

        # CREATE FILENAME TO new_filename_to_save
        new_index = int(files[-4].split(".")[1]) + 1  # GET last remote_log_saved with index AND GET new index
        temp = f'{files[-3]}'.split("_")
        new_filename_to_save = f'{temp[0]}_{temp[1]}_remote_log_saved.{new_index}'

        # RENAME remote_log_2 to new name with new index
        os.rename(fr'{LOG_FOLDER}{files[-3]}', fr'{LOG_FOLDER}{new_filename_to_save}')

    else:
        # DELETE remote_log_2
        for fname in os.listdir(LOG_FOLDER):
            if fname.endswith('remote_log_2.log'):
                os.remove(f'{LOG_FOLDER}{fname}')


@rerun
def generate_logs_for_adding_to_db():

    ### 1) DELETE previous file ###
    filenames = os.listdir(LOGS_TO_PARSE_FOLDER)  # GET ALL FILE NAMES IN DIRECTORY
    for filename in filenames:
        if filename.startswith('previous'):
            os.remove(f'{LOGS_TO_PARSE_FOLDER}{filename}')
    ### end of 1 ##################

    ### 2) Rename new_... to previous_... ###
    filenames = os.listdir(LOGS_TO_PARSE_FOLDER)
    oldNameToNew = [filename for filename in filenames if filename.startswith('new')][0]  # GET filename start with new_...
    newNameToNew = oldNameToNew.replace('new', 'previous')  # Rename filename start with new_... to previous_...
    os.rename(fr'{LOGS_TO_PARSE_FOLDER}{oldNameToNew}', fr'{LOGS_TO_PARSE_FOLDER}{newNameToNew}')
    ### end of 2 ############################


    ### 3) concatenate remote_log_0 and remote_log_1 and save to new_... ###
    filenames = os.listdir(LOG_FOLDER)  # GET ALL FILE NAMES IN DIRECTORY
    current_log_0_name = filenames[-1]
    current_log_1_name = filenames[-2]
    filenames = [current_log_1_name, current_log_0_name]
    current_log_0_name = current_log_0_name.replace('.log', '')
    current_log_1_name = current_log_1_name.replace('.log', '')
    newFilename = f'new_{current_log_1_name}+{current_log_0_name}.log'

    filepath = os.path.join(LOGS_TO_PARSE_FOLDER, newFilename)
    with open(filepath, 'w') as outfile:
        for filename in filenames:
            filepath = os.path.join(LOG_FOLDER, filename)
            with open(filepath) as infile:
                for line in infile:
                    outfile.write(line)
    ### end of 3 ############################################################


    ### 4) get lines only from a new file and save to logsForAddingToDB.log ###
    filenames = os.listdir(LOGS_TO_PARSE_FOLDER)  # GET ALL FILE NAMES IN DIRECTORY

    previousFilepath = os.path.join(LOGS_TO_PARSE_FOLDER,
                                    [filename for filename in filenames if filename.startswith('previous')][0])
    newFilepath = os.path.join(LOGS_TO_PARSE_FOLDER,
                               [filename for filename in filenames if filename.startswith('new')][0])

    previousFile = open(previousFilepath).readlines()
    newFile = open(newFilepath).readlines()
    with open(f'{LOGS_TO_PARSE_FOLDER}logsForAddingToDB.log', 'w') as outfile:
        with open(f'{LOGS_TO_PARSE_FOLDER}temp_logsForAddingToDB.log', 'a') as temp_outfile:
            for line in difflib.unified_diff(previousFile, newFile):
                if line[0] == "+" and line[1] != "+":
                    outfile.write(line[1:])
                    temp_outfile.write(line[1:])
    ### end of 4 #################################################################


isEmailSend_database = False


def add_to_database(listOpenedConnect, listClosedConnect):
    db_connection = psycopg2
    global isEmailSend_database

    try:
        #  READ PARAMETERS FROM JSON
        with open("parameters.txt", "r") as file:
            data = json.loads(file.read())
        db_connection = psycopg2.connect(user=data['postgreSQL']['user'],
                                         password=data['postgreSQL']['password'],
                                         host=data['postgreSQL']['host'],
                                         port=data['postgreSQL']['port'],
                                         database=data['postgreSQL']['database'])
        db_cursor = db_connection.cursor()
        db_connection.autocommit = True

        for item in listOpenedConnect:
            postgres_insert_query = f" SELECT full_name, is_fired FROM workers " \
                                    f" WHERE client_id = {item['client_id']} "
            db_cursor.execute(postgres_insert_query)
            full_name, is_fired = db_cursor.fetchone()
            full_name = full_name.strip()
            postgres_insert_query = """ INSERT INTO statistics
            (connection_number, start_connection, client_id, full_name, is_fired,
            local_source_IP, local_destination_ip, remote_ip, remote_port)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
            record_to_insert = (item['connection_number'], item['datetime'], item['client_id'], full_name, is_fired,
                                item['localSourceIP'], item['localDestinationIP'], item['remoteIP'], item['remotePort'])
            db_cursor.execute(postgres_insert_query, record_to_insert)

        for item in listClosedConnect:
            postgres_insert_query = f" SELECT start_connection FROM statistics " \
                                    f" WHERE connection_number = {item['connection_number']} " \
                                    f" ORDER BY start_connection DESC"
            db_cursor.execute(postgres_insert_query)
            record = db_cursor.fetchone()
            if record:
                postgres_insert_query = f" UPDATE statistics " \
                                        f" SET end_connection = %s ," \
                                        f"     connection_time = %s ," \
                                        f"     bytes_sent = %s ," \
                                        f"     bytes_received = %s ," \
                                        f"     total_traffic = %s " \
                                        f" FROM (SELECT * FROM statistics " \
                                        f" Where connection_number = {item['connection_number']} " \
                                        f" ORDER BY start_connection DESC " \
                                        f" LIMIT 1) as sub " \
                                        f" Where statistics.start_connection = sub.start_connection"
                record_to_insert = (item['datetime'], item['datetime'] - record[0], item['bytes_sent'],
                                    item['bytes_received'], item['bytes_sent'] + item['bytes_received'])
                db_cursor.execute(postgres_insert_query, record_to_insert)

        if (db_connection):
            db_cursor.close()
            db_connection.close()

            # DELETE temp_logsForAddingToDB.log
            for filename in os.listdir(LOGS_TO_PARSE_FOLDER):
                if filename.startswith('temp_logsForAddingToDB.log'):
                    os.remove(f'{LOGS_TO_PARSE_FOLDER}{filename}')

        if isEmailSend_database:
            now = datetime.now()
            dt_string = now.strftime("%d.%m.%Y %H:%M:%S")
            send_email(f'Successfully insert records into database table {get_my_local_ip()}',
                       f'No errors found',
                       f'Operations with database is available again since last check = {dt_string}')
            isEmailSend_database = False

    except (Exception, psycopg2.Error) as error:
        if(db_connection):
            if not isEmailSend_database:
                now = datetime.now()
                dt_string = now.strftime("%d.%m.%Y %H:%M:%S")
                send_email(f'Failed to insert BelVPNGate log records into database table {get_my_local_ip()}',
                           str(error).strip(),
                           f'Operations with database not available from last check = {dt_string}\n\n'
                           f'All logs will be added to a temporary file "temp_logsForAddingToDB.log"\n'
                           f'Upon successful connection to the database, these logs will be written to the database')
                isEmailSend_database = True
            print("Database error: ", str(error).strip())


def parse_log_add_to_database():
    FILENAME = "temp_logsForAddingToDB.log"
    listOpenedConnect = []
    listClosedConnect = []
    filepath = os.path.join(LOGS_TO_PARSE_FOLDER, FILENAME)
    with open(filepath) as infile:
        for i, line in enumerate(infile):
            data = line.split()
            # 00100119 - start of connections, 0010011d - end of connections
            if len(data) >= 5 and (data[5] == '00100119' or data[5] == '0010011d'):
                # 00100119 - start of connections
                if data[5] == '00100119':
                    localDestinationIP, localSourceIP = data[13].replace(',','').split("->")
                    remoteIP, remotePort = data[15].replace(',', '').split(":")
                    *_, client_id = data[17].split(",")[0].replace('"CN=','').split("_")
                    tempOpenConnDict = {'msg_id': data[5],
                                        'datetime': datetime.strptime(f'{datetime.now().year} {data[0]} {data[1]} {data[2]}',
                                                                      '%Y %b %d %H:%M:%S'),
                                        'connection_number': int(data[9]),
                                        'localSourceIP': localSourceIP,
                                        'localDestinationIP': localDestinationIP,
                                        'remoteIP': remoteIP,
                                        'remotePort': int(remotePort),
                                        'client_id': int(client_id)
                                        }
                    listOpenedConnect.append(tempOpenConnDict)
                # 0010011d - end of connections
                if data[5] == '0010011d':
                    tempClosConnDict = {'msg_id': data[5],
                                        'datetime': datetime.strptime(f'{datetime.now().year} {data[0]} {data[1]} {data[2]}',
                                                                      '%Y %b %d %H:%M:%S'),
                                        'connection_number': int(data[8]),
                                        'bytes_sent': int(data[10]),
                                        'bytes_received': int(data[13])
                                        }
                    listClosedConnect.append(tempClosConnDict)

    add_to_database(listOpenedConnect, listClosedConnect)


def sleep_for(seconds):
    if seconds <= 0:
        return
    start_division = seconds / 10 if seconds >= 10 else 10 / seconds
    division = start_division
    done = 0
    undone = 10
    for i in range(seconds):
        if i <= division and seconds < 10:
            division += start_division
            done += int(start_division)
            undone -= int(start_division)
        if i >= division and seconds >= 10:
            division += start_division
            done += 1
            undone -= 1
        sys.stdout.write(f"\r{round(i*100/seconds,1):>4}% [{'=' * done}{' ' * undone}]"
                         f" Waiting for {seconds - i} seconds ...")
        sys.stdout.flush()
        time.sleep(1)

    sys.stdout.write("\r")
    sys.stdout.flush()


if __name__ == '__main__':

    #  MAKING A CONNECTION
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    create_connection(ssh, 'gate')
    ftp_client = ssh.open_sftp()

    while True:
        if not ssh.get_transport().is_active():
            ssh.close()
            print(f'Current ssh connection closed and try to reopen')
            create_connection(ssh, 'gate')
        if ssh.get_transport().is_active():
            get_remote_files()
            # print(f'Remote files received at : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            check_similar_files()
            # print(f'Similar files checked at : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            generate_logs_for_adding_to_db()
            # print(f'Logs for adding to DB, create at : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'Received and checked, Logs create: '
                  f'{datetime.now().strftime("%d.%m.%Y %H:%M:%S")}')
            parse_log_add_to_database()
            # print()
        sleep_for(60)  # delay for 1 minute

    ftp_client.close()
    ssh.close()
