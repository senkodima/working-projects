import os
import difflib
import json
import schedule
import time
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from socket import gaierror
from operator import itemgetter
from enum import Enum


class Files(Enum):
    user_wrong_pass = 'user_wrong_pass.csv'
    user_block = 'user_block.csv'
    fail_user_wrong_pass = 'fail-user_wrong_pass.csv'


def is_good_ipv4(s):
    pieces = s.split('.')
    if len(pieces) != 4:
        return False
    try:
        return all(0 <= int(p) < 256 for p in pieces)
    except ValueError:
        return False


def get_ip_info(ip):
    url = f"https://geolite.info/geoip/v2.1/city/{ip}"
    with open("parameters.txt", "r") as file:
        params = json.loads(file.read())
    request = requests.get(url, auth=(params["maxmind"]["account_id"],
                                      params["maxmind"]["license_key"]))
    status_code = request.status_code
    ip_info = ''
    result = ''
    if status_code != 404:
        result = request.json()
        # print('JSON:\n', json.dumps(result, indent=4, ensure_ascii=False))
    if str(status_code).startswith('4') or \
            str(status_code).startswith('5'):
        if 'code' in result:
            if result['code'] == 'IP_ADDRESS_RESERVED':
                ip_info += 'Зарезервированный IP-адресс'
        print('bad status code : ', result)
    else:
        if 'continent' in result:
            if 'names' in result['continent']:
                continent = result['continent']['names']['ru'] \
                    if 'ru' in result['continent']['names'] \
                    else result['continent']['names']['en']
                ip_info += f'{continent} '
        if 'country' in result:
            if 'names' in result['country']:
                country = result['country']['names']['ru'] \
                    if 'ru' in result['country']['names'] \
                    else result['country']['names']['en']
                ip_info += f'{country} '
        if 'city' in result:
            if 'names' in result['city']:
                city = result['city']['names']['ru'] \
                    if 'ru' in result['city']['names'] \
                    else result['city']['names']['en']
                ip_info += f'{city} '
        if 'subdivisions' in result:
            if 'names' in result['subdivisions']:
                subdivisions = result['subdivisions']['names']['ru'] \
                    if 'ru' in result['subdivisions']['names'] \
                    else result['subdivisions']['names']['en']
                ip_info += f'{subdivisions} '
        if 'traits' in result:
            if 'autonomous_system_organization' in result['traits']:
                organization = result['traits']['autonomous_system_organization']
                ip_info += f';{organization};'
            if 'network' in result['traits']:
                network = result['traits']['network']
                ip_info += f'{network}'

    return ip_info


def plain_to_html(bodyText):

    temp_lines = '''<!DOCTYPE html>
        <html>
            <head>
                <meta charset="utf-8">
                <style>
                    table {
                      border-collapse: collapse;
                    }

                    td, th {
                      border: 1px solid #dddddd;
                      text-align: left;
                      padding: 8px;
                    }

                </style>
            </head>
            <body>

        '''
    lines = bodyText.split('\n')
    for i, line in enumerate(lines):
        line = line.replace(';', '<br>')
        if 'кол-во' in line:
            temp = '<table><tr>\n'
            for word in line.split(' | '):
                word = '<th>' + word.strip() + '</th>\n'
                temp += word
            line = temp + '</tr>\n'
        if '|' in line:
            temp = '<tr>\n' if 'Беларусь' in line else '<tr style="background-color:#FFFF99">\n'
            for word in line.split(' | '):
                word = '<td>' + word + '</td>\n'
                temp += word
            line = temp + '</tr>'
            if i + 1 <= len(lines) - 1:
                if '|' not in lines[i + 1]:
                    line += '</table>'
        if 'Файл' in line:
            line = '<strong>' + line + '</strong>'

        temp_words = ''
        for word in line.split(' '):
            temp_words += word + ' '
        if '<tr' in temp_words:
            temp_lines += temp_words
        else:
            temp_lines += temp_words + '<br>'

    bodyText = temp_lines + '\n' + '</body>' + '\n' + '</html>'
    return bodyText


def send_email(bodyText, subject):
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

        carbon_copy = f"{data['email']['seklickij']}," \
                      f"{data['email']['lepekha']}"

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = receiver
        message['CC'] = carbon_copy

        # write the HTML part
        html_bodyText = plain_to_html(bodyText)
        # convert both parts to MIMEText objects and add them to the MIMEMultipart message
        part1 = MIMEText(bodyText, "plain")
        part2 = MIMEText(html_bodyText, "html")
        message.attach(part1)
        message.attach(part2)

        list_receiver = list(receiver.split(","))
        list_carbon_copy = list(carbon_copy.split(","))
        # send your message with credentials specified above
        with smtplib.SMTP_SSL(smtp_server, port) as server:
            server.login(username, password)
            server.sendmail(sender, list_receiver + list_carbon_copy, message.as_string())
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


def get_portal_logs_ip():
    with open("parameters.txt", "r") as file:
        data = json.loads(file.read())
    return data['portal_logs']['ip']


PATH_TO_STATISTICS = f"//{get_portal_logs_ip()}/stat/"
PORTAL_LOG_FOLDER = "D:/script_Portal/"


def day_report():
    now = datetime.now()
    current_date = now.date()
    yesterday_date = current_date - timedelta(days=1)

    body_text = ''
    empty_str = '""\n'
    no_rows_str = '"no rows selected"\n'
    rows_selected_str = "rows selected."
    first_line1 = '"SQL> @/data/log/stat_var1_command.sql"\n'
    first_line2 = '"SQL> @/data/log/stat_var2_command.sql"\n'
    first_line3 = '"SQL> @/data/log/stat_var3_command.sql"\n'
    last_line = '"SQL> SPOOL OFF"\n'

    path_fail_user_wrong_pass = f"{PATH_TO_STATISTICS}{yesterday_date}/{yesterday_date}_fail-user_wrong_pass.csv"
    file_fail_user_wrong_pass = open(path_fail_user_wrong_pass).readlines()

    str_user_wrong_pass = fr"{PATH_TO_STATISTICS}{yesterday_date}/{yesterday_date}_user_wrong_pass.csv"
    if os.path.exists(str_user_wrong_pass):
        with open(str_user_wrong_pass, 'r') as file:
            temp_user_wrong_pass = 'Файл: user_wrong_pass\n' \
                                   'Общее суточное количество попыток неправильного ввода пароля (для любых учетных записей - существующих и несуществующих).\n' \
                                   'IP-адрес | логин | неверный | кол-во | информация об IP-адресе\n'
            temp_list = []
            for line in file:
                if line != empty_str and line != no_rows_str and rows_selected_str not in line\
                        and line != first_line1 and line != last_line:
                    wrong = '👤логин' if line in file_fail_user_wrong_pass else 'пароль🔒'
                    data = line[1:-2].split('","')
                    ip_info = get_ip_info(data[0]) if is_good_ipv4(data[0]) else ""
                    temp_list.append((data[0], data[1], wrong, int(data[2]), ip_info))
            temp_list = sorted(temp_list, key=itemgetter(3), reverse=True)
            temp = ""
            for element in temp_list:
                temp += f'{element[0]} | {element[1]} | {element[2]} | {element[3]} | {element[4]}\n'
            if temp:
                temp_user_wrong_pass += temp
                body_text += temp_user_wrong_pass
    else:
        print(f"{str_user_wrong_pass} does not exist")

    str_user_block = fr"{PATH_TO_STATISTICS}{yesterday_date}/{yesterday_date}_user_block.csv"
    if os.path.exists(str_user_block):
        with open(str_user_block, 'r') as file:
            temp_user_block = '\nФайл: user_block\n' \
                              'Общее суточное количество событий блокировки пользователя при превышении лимита неправильных попыток ввода.\n' \
                              'логин | кол-во\n'

            temp_list = []
            for line in file:
                if line != empty_str and line != no_rows_str and rows_selected_str not in line\
                        and line != first_line2 and line != last_line:
                    data = line[1:-2].split('","')
                    temp_list.append((data[0], int(data[1])))
            temp_list = sorted(temp_list, key=itemgetter(1), reverse=True)
            temp = ""
            for element in temp_list:
                temp += f'{element[0]} | {element[1]}\n'
            if temp:
                temp_user_block += temp
                temp_user_block += "\n\tПримечание:\n" \
                                   "\tЛимит 10 неправильных попыток, блокировка на 30 минут.\n" \
                                   "\tЕсли за 24 часа (период сброса счетчика попыток), " \
                                   "количество неправильных попыток меньше 10 и период этот истек, счетчик неправильных попыток обнуляется.\n" \
                                   "\tЛогин вида avest-XXXXXXXXX-XXXXXXXXXXXpbX - это ЭЦП (попытки входа с ЭЦП), " \
                                   "который у нас ещё не зарегистрован в виде учетной записи.\n"
                body_text += temp_user_block
    else:
        print(f"{str_user_block} does not exist")

    if body_text:
        body_text = 'Суточный отчет за: ' + str(yesterday_date.strftime("%d.%m.%Y"))\
                    + '\n\n' \
                    + body_text
        send_email(body_text, "Суточные неудачные попытки авторизации - portal.gov.by")

    now = datetime.now()
    print('day report at:', now)


def job(yesterday_flag=None):
    if not os.path.exists(PATH_TO_STATISTICS):
        print(f"{PATH_TO_STATISTICS} does not exist")
        return
    if not os.path.exists(PORTAL_LOG_FOLDER):
        print(f"{PORTAL_LOG_FOLDER} does not exist")
        return

    ### 1) DELETE previous file ###
    filenames = os.listdir(PORTAL_LOG_FOLDER)  # GET ALL FILE NAMES IN DIRECTORY
    for filename in filenames:
        if filename.startswith('previous'):
            os.remove(f'{PORTAL_LOG_FOLDER}{filename}')
    ### end of 1 ##################

    ### 2) Rename current_... to previous_... ###
    filenames = os.listdir(PORTAL_LOG_FOLDER)
    for filename in filenames:
        if filename.startswith('current'):
            new_filename = filename.replace('current',
                                            'previous')  # Rename filename start with current_... to previous_...
            os.rename(fr'{PORTAL_LOG_FOLDER}{filename}', fr'{PORTAL_LOG_FOLDER}{new_filename}')
    ### end of 2 ############################

    now = datetime.now()
    current_date = now.date()
    yesterday_date = current_date - timedelta(days=1)

    for filename in Files:
        str_file_pass = fr"{PATH_TO_STATISTICS}{current_date}/{current_date}_{filename.value}" \
            if not yesterday_flag \
            else fr"{PATH_TO_STATISTICS}{yesterday_date}/{yesterday_date}_{filename.value}"
        if os.path.exists(str_file_pass):
            with open(str_file_pass, 'r') as file:
                output = os.path.join(PORTAL_LOG_FOLDER, f'current_{filename.value[:-4]}.txt')
                with open(output, 'w') as output:
                    for line in file:
                        output.write(line)
        else:
            print(f"{str_file_pass} does not exist")


    start_time = f'00:00' if not yesterday_flag else f'{yesterday_date.strftime("%d.%m.%Y")} 00:00'
    end_time = f'{now.strftime("%H:%M")}' if not yesterday_flag else f'{now.strftime("%d.%m.%Y %H:%M")}'
    start_to_end = f'(с {start_time} по {end_time})'

    body_text = ''
    empty_str = '""\n'
    no_rows_str = '"no rows selected"\n'
    rows_selected_str = "rows selected."


    previousFilepath_user_wrong_pass = os.path.join(PORTAL_LOG_FOLDER, 'previous_user_wrong_pass.txt')
    currentFilepath_user_wrong_pass = os.path.join(PORTAL_LOG_FOLDER, 'current_user_wrong_pass.txt')
    previousFile = open(previousFilepath_user_wrong_pass).readlines()
    currentFile = open(currentFilepath_user_wrong_pass).readlines()
    currentFilepath_fail_user_wrong_pass = os.path.join(PORTAL_LOG_FOLDER, 'current_fail-user_wrong_pass.txt')
    currentFile_fail_user_wrong_pass = open(currentFilepath_fail_user_wrong_pass).readlines()
    temp_user_wrong_pass = f'Файл: user_wrong_pass\n' \
        f'Количество попыток (+n) за последний час.\n' \
        f'Предыдущее → Текущее {start_to_end} количество общих попыток неправильного ввода.\n' \
        f'IP-адрес | логин | неверный | кол-во | информация об IP-адресе\n'
    temp_list = []
    previousCount = 0
    for line in difflib.unified_diff(previousFile, currentFile):
        if line[0] == "-" and line[1] != "-":
            if line[1:] != empty_str and line[1:] != no_rows_str and rows_selected_str not in line[1:]:
                previousCount = int(line[2:-2].split('","')[2])
        if line[0] == "+" and line[1] != "+":
            if line[1:] != empty_str and line[1:] != no_rows_str and rows_selected_str not in line[1:]:
                wrong = '👤логин' if line[1:] in currentFile_fail_user_wrong_pass else 'пароль🔒'
                data = line[2:-2].split('","')
                currentCount = int(data[2])
                delta = f'+{currentCount - previousCount};{previousCount} → {currentCount}'
                ip_info = get_ip_info(data[0]) if is_good_ipv4(data[0]) else ""
                temp_list.append((data[0], data[1], wrong, int(data[2]), delta, ip_info))
                previousCount = 0

    temp_list = sorted(temp_list, key=itemgetter(3), reverse=True)
    temp = ""
    for element in temp_list:
        temp += f'{element[0]} | {element[1]} | {element[2]} | {element[4]} | {element[5]}\n'
    if temp:
        temp_user_wrong_pass += temp
        body_text += temp_user_wrong_pass


    previousFilepath_user_block = os.path.join(PORTAL_LOG_FOLDER, 'previous_user_block.txt')
    currentFilepath_user_block = os.path.join(PORTAL_LOG_FOLDER, 'current_user_block.txt')
    previousFile = open(previousFilepath_user_block).readlines()
    currentFile = open(currentFilepath_user_block).readlines()
    temp_user_block = f'\nФайл: user_block\n' \
        f'Количество попыток (+n) за последний час.\n' \
        f'Предыдущее → Текущее {start_to_end} количество общих событий блокировки пользователя ' \
                      f'при превышении лимита неправильных попыток ввода.\n' \
        f'логин | кол-во\n'
    temp_list = []
    previousCount = 0
    for line in difflib.unified_diff(previousFile, currentFile):
        if line[0] == "-" and line[1] != "-":
            if line[1:] != empty_str and line[1:] != no_rows_str and rows_selected_str not in line[1:]:
                previousCount = int(line[2:-2].split('","')[1])
        if line[0] == "+" and line[1] != "+":
            if line[1:] != empty_str and line[1:] != no_rows_str and rows_selected_str not in line[1:]:
                data = line[2:-2].split('","')
                currentCount = int(data[1])
                delta = f'+{currentCount - previousCount};{previousCount} → {currentCount}'
                temp_list.append((data[0], int(data[1]), delta))
                previousCount = 0
    temp_list = sorted(temp_list, key=itemgetter(1), reverse=True)
    temp = ""
    for element in temp_list:
        temp += f'{element[0]} | {element[2]}\n'
    if temp:
        temp_user_block += temp
        temp_user_block += "\n\tПримечание:\n" \
            "\tЛимит 10 неправильных попыток, блокировка на 30 минут.\n" \
            "\tЕсли за 24 часа (период сброса счетчика попыток), " \
            "количество неправильных попыток меньше 10 и период этот истек, счетчик неправильных попыток обнуляется.\n" \
            "\tЛогин вида avest-XXXXXXXXX-XXXXXXXXXXXpbX - это ЭЦП (попытки входа с ЭЦП), " \
            "который у нас ещё не зарегистрован в виде учетной записи.\n"
        body_text += temp_user_block

    if body_text:
        send_email(body_text, "Неудачные попытки авторизации - portal.gov.by")

    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    print(now)


schedule.every().day.at("00:25").do(day_report)
schedule.every().day.at("00:20").do(job, True)
schedule.every().hour.at(":35").do(job)
# нужно для запуска планировщика с периодом в 1 секунду:
while True:
    schedule.run_pending()
    time.sleep(1
