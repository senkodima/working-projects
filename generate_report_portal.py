import os
import json
import re
import xlsxwriter
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from datetime import datetime
from socket import gaierror
from email import encoders


def get_portal_logs_ip():
    with open("parameters.txt", "r") as file:
        data = json.loads(file.read())
    return data['portal_logs']['ip']


PATH_TO_STATISTICS = f"//{get_portal_logs_ip()}/stat/"
PORTAL_LOG_FOLDER = "D:/script_Portal/"


def send_email(body, subject, file_path, file_name):
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
        receiver = data['email']['self_receiver']

        # Create a multipart message and set headers
        message = MIMEMultipart()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = receiver

        # Add body to email
        message.attach(MIMEText(body, "plain"))

        # Open file in binary mode
        with open(file_path, "rb") as attachment:
            # Add file as application/octet-stream
            # Email client can usually download this automatically as attachment
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())

        # Encode file in ASCII characters to send by email
        encoders.encode_base64(part)

        # Add header as key/value pair to attachment part
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {file_name}",
        )

        # Add attachment to message and convert message to string
        message.attach(part)
        text = message.as_string()

        # Log in to server using secure context and send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(username, password)
            server.sendmail(sender, receiver, text)

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


def generate_report_portal():
    if not os.path.exists(PATH_TO_STATISTICS):
        print(f"{PATH_TO_STATISTICS} does not exist")
        return
    if not os.path.exists(PORTAL_LOG_FOLDER):
        print(f"{PORTAL_LOG_FOLDER} does not exist")
        return

    filenames = sorted(os.listdir(PATH_TO_STATISTICS))
    clean_filenames = []
    for file in filenames:
        pattern = re.compile("[0-9]{4}-[0-9]{2}-[0-9]{2}")
        if pattern.match(file):
            clean_filenames.append(file)

    ### 1) DELETE old report file ###
    filenames = os.listdir(PORTAL_LOG_FOLDER)  # GET ALL FILE NAMES IN DIRECTORY
    for filename in filenames:
        if filename.startswith('summary_report'):
            os.remove(f'{PORTAL_LOG_FOLDER}{filename}')
    ### end of 1 ##################

    empty_str = '""\n'
    no_rows_str = '"no rows selected"\n'
    rows_selected_str = "rows selected."
    first_line1 = '"SQL> @/data/log/stat_var1_command.sql"\n'
    first_line2 = '"SQL> @/data/log/stat_var2_command.sql"\n'
    first_line3 = '"SQL> @/data/log/stat_var3_command.sql"\n'
    last_line = '"SQL> SPOOL OFF"\n'

    temp_list = []

    for clean_filename in clean_filenames:
        path_user_wrong_pass = f'{PATH_TO_STATISTICS}{clean_filename}/{clean_filename}_user_wrong_pass.csv'
        path_fail_user_wrong_pass = f"{PATH_TO_STATISTICS}{clean_filename}/{clean_filename}_fail-user_wrong_pass.csv"
        file_user_wrong_pass = open(path_user_wrong_pass).readlines()
        file_fail_user_wrong_pass = open(path_fail_user_wrong_pass).readlines()
        for line in file_user_wrong_pass:
            if line != empty_str and line != no_rows_str and rows_selected_str not in line \
                    and line != first_line1 and line != first_line2 and line != first_line3 \
                    and line != last_line:
                wrong = '👤логин' if line in file_fail_user_wrong_pass else 'пароль🔒'
                line = line.replace('\n', '')
                line = line + f',"{clean_filename}"'
                line = line[1:-1]
                temp = line.split('","')
                temp.insert(2, wrong)
                temp_list.append(temp)

    # открываем новый файл на запись
    workbook = xlsxwriter.Workbook(os.path.join(PORTAL_LOG_FOLDER, 'summary_report.xlsx'))
    # создаем там "лист"
    worksheet = workbook.add_worksheet(f"с {clean_filenames[0]} по {clean_filenames[-1]}")

    cell_format = workbook.add_format({'bold': True, 'text_wrap': True, 'align': 'vcenter'})
    cell = workbook.add_format({'text_wrap': True, 'align': 'vcenter'})

    worksheet.autofilter('A1:L1')

    worksheet.write(f'A1', '№', cell_format)
    worksheet.write(f'B1', 'IP', cell_format)
    worksheet.write(f'C1', 'Логин', cell_format)
    worksheet.write(f'D1', 'Неверный', cell_format)
    worksheet.write(f'E1', 'Кол-во', cell_format)
    worksheet.write(f'F1', 'Дата', cell_format)

    worksheet.write(f'I1', 'Кол-во логинов', cell_format)
    worksheet.write(f'J1', 'Кол-во паролей', cell_format)
    worksheet.write(f'K1', 'Общее кол-во', cell_format)
    worksheet.write(f'L1', 'Дата', cell_format)

    worksheet.set_row(0, 30)  # first row

    worksheet.set_column(0, 0, 6)  # A
    worksheet.set_column(1, 1, 15)  # B
    worksheet.set_column(2, 2, 40)  # C
    worksheet.set_column(3, 3, 12)  # D
    worksheet.set_column(4, 4, 5)  # E
    worksheet.set_column(5, 5, 8)  # F

    worksheet.set_column(6, 6, 2)  # G
    worksheet.set_column(7, 7, 2)  # H

    worksheet.set_column(8, 8, 10)  # I
    worksheet.set_column(9, 9, 10)  # J
    worksheet.set_column(10, 10, 9)  # K
    worksheet.set_column(11, 11, 8)  # L

    worksheet.freeze_panes(1, 6)

    for i, (IP, login, wrong, count, date) in enumerate(temp_list, start=2):
        worksheet.write(f'A{i}', int(i-1))
        worksheet.write(f'B{i}', IP)
        worksheet.write(f'C{i}', login, cell)
        worksheet.write(f'D{i}', wrong)
        worksheet.write(f'E{i}', int(count))
        date_time = datetime.strptime(f'{date}', '%Y-%m-%d')
        date_format = workbook.add_format({'num_format': 'dd.mm.yy'})
        worksheet.write(f'F{i}', date_time, date_format)

    i = 2
    login = '👤логин'
    password = 'пароль🔒'
    login_counter = 0
    password_counter = 0
    counter = 0
    for j in range(1, len(temp_list)):
        if temp_list[j][4] == temp_list[j - 1][4]:
            counter += int(temp_list[j-1][3])
            if temp_list[j-1][2] == login:
                login_counter += int(temp_list[j-1][3])
            if temp_list[j-1][2] == password:
                password_counter += int(temp_list[j-1][3])
        if temp_list[j][4] != temp_list[j - 1][4]:
            counter += int(temp_list[j-1][3])
            if temp_list[j-1][2] == login:
                login_counter += int(temp_list[j-1][3])
            if temp_list[j-1][2] == password:
                password_counter += int(temp_list[j - 1][3])
            worksheet.write(f'I{i}', int(login_counter))
            worksheet.write(f'J{i}', int(password_counter))
            worksheet.write(f'K{i}', int(counter))
            date_time = datetime.strptime(f'{temp_list[j-1][4]}', '%Y-%m-%d')
            date_format = workbook.add_format({'num_format': 'dd.mm.yy'})
            worksheet.write(f'L{i}', date_time, date_format)
            login_counter = 0
            password_counter = 0
            counter = 0
            i += 1
        if j == len(temp_list)-1:
            counter += int(temp_list[j][3])
            if temp_list[j][2] == login:
                login_counter += int(temp_list[j][3])
            if temp_list[j][2] == password:
                password_counter += int(temp_list[j][3])
            worksheet.write(f'I{i}', int(login_counter))
            worksheet.write(f'J{i}', int(password_counter))
            worksheet.write(f'K{i}', int(counter))
            date_time = datetime.strptime(f'{temp_list[j - 1][4]}', '%Y-%m-%d')
            date_format = workbook.add_format({'num_format': 'dd.mm.yy'})
            worksheet.write(f'L{i}', date_time, date_format)
            i += 1

    # сохраняем и закрываем
    workbook.close()

    file_path = f'{PORTAL_LOG_FOLDER}summary_report.xlsx'
    if not os.path.exists(file_path):
        print(f"{file_path} does not exist")
        return

    file_name = file_path.split('/')[-1]

    send_email(f"Отчет с {clean_filenames[0]} по {clean_filenames[-1]}",
               "Суммарный отчет по неудачным попыткам авторизации - portal.gov.by",
               file_path, file_name)


if __name__ == '__main__':
    generate_report_portal()

