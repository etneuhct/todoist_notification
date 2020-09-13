from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import todoist
from datetime import datetime
from collections import OrderedDict
import smtplib
from jinja2 import Template
import json
import time


def list_to_dict(elements):
    return {element['id']: element for element in elements}


def str_to_date(date_str):
    if 'T' in date_str:
        date_str = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
    else:
        date_str = datetime.strptime(date_str, '%Y-%m-%d')
    return date_str


def get_due_tasks(items):
    result = [item for item in items if item['checked'] == 0]
    return sorted(result, key=lambda x: str_to_date(x['due']['date']) if x['due'] else datetime.now())


def get_tree(tasks, projects):
    result = OrderedDict()
    for task in tasks:
        if task['project_id'] not in result:
            result[task['project_id']] = projects[task['project_id']]
            result[task['project_id']]['tasks'] = OrderedDict()
        result[task['project_id']]['tasks'][task['id']] = task
    return result


def get_text_message(full_name, data, tasks):
    result = "Bonjour {}.\nIl reste encore {} tache(s) à compléter".format(full_name, len(tasks))
    for project_key in data:
        project_message = "Projet: {}".format(data[project_key]['name'])
        result = "{}\n{}".format(result, project_message)
        tasks = data[project_key]['tasks']
        for task in tasks:
            task_message = "- \"{}\" créée le {}.".format(tasks[task]['content'], tasks[task]['date_added'])
            if tasks[task]['due']:
                task_message = task_message + " A rendre le {}".format(tasks[task]['due']['date'])
            result = "{}\n{}".format(result, task_message)
    return result


def get_html_message(full_name, data, tasks):
    with open('message_template.html', 'rb') as template:
         template = template.read().decode()
    html = Template(template).render(name=full_name, projects=data, tasks=tasks)
    return html


def start_mail_server(content, user_login, user_password, message_receivers, content_format):
    mail_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    mail_server.ehlo()
    try:
        mail_server.login(user_login, user_password)
    except smtplib.SMTPAuthenticationError:
        print("Invalid Log")
        mail_server.quit()
        return
    msg = MIMEMultipart()
    msg['Subject'] = "Your todoist tasks"
    msg.attach(MIMEText(content, content_format))
    try:
        mail_server.sendmail(from_addr='', to_addrs=message_receivers, msg=msg.as_string())
    except smtplib.SMTPRecipientsRefused:
        print("Wrong receivers")
        mail_server.quit()
        return
    mail_server.quit()


def load_setting():
    with open("settings.json", 'r') as setting_file:
        return json.load(setting_file)


def check_todo(settings):

    api = todoist.TodoistAPI(settings['token'])
    api.sync()
    if not api.state['user']:
        print("Invalid todoist api key")
        return
    else:
        preferred_format = settings['preferred_format']
        name = api.state['user']['full_name']
        due_tasks = get_due_tasks(api.items.all())
        if len(due_tasks) > 0:
            projects_data = list_to_dict(api.projects.all())
            tree = get_tree(due_tasks, projects_data)
            message = get_text_message(name, tree, due_tasks)\
                if preferred_format == 'plain'\
                else get_html_message(name, tree, due_tasks)
            start_mail_server(message, settings['mail'], settings['password'], settings['receivers'], preferred_format)


if __name__ == "__main__":
    setting = load_setting()
    while True:
        check_todo(setting)
        time.sleep(setting['time_between'] * 3600)