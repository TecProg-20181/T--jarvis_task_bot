#!/usr/bin/env python3

import json
import requests
import time
import urllib
from datetime import datetime

import sqlalchemy

import db
from db import Task
from jarvistoken import *
from contracts import contract

URL = "https://api.telegram.org/bot{}/".format(get_token())
REPO_OWNER = 'TecProg-20181'
REPO_NAME = 'T--jarvis_task_bot'

HELP = """
 /new NOME
 /todo ID
 /doing ID
 /done ID
 /delete ID
 /list
 /rename ID NOME
 /dependson ID ID...
 /duplicate ID
 /priority ID PRIORITY{low, medium, high}
 /duedate ID DATE
 /create_issue ID
 /help
"""


@contract(url='str')
def get_url(url):
    response = requests.get(url)
    content = response.content.decode("utf8")
    return content

@contract(url='str')
def get_json_from_url(url):
    content = get_url(url)
    js = json.loads(content)
    return js

def get_updates(offset=None):
    url = URL + "getUpdates?timeout=100"
    if offset:
        url += "&offset={}".format(offset)
    js = get_json_from_url(url)
    return js

@contract(text='str', chat_id='int')
def send_message(text, chat_id, reply_markup=None):
    text = urllib.parse.quote_plus(text)
    url = URL + "sendMessage?text={}&chat_id={}&parse_mode=Markdown".format(text, chat_id)
    if reply_markup:
        url += "&reply_markup={}".format(reply_markup)
    get_url(url)

@contract(update='list')
def get_last_update_id(updates):
    update_ids = []
    for update in updates["result"]:
        update_ids.append(int(update["update_id"]))

    return max(update_ids)

@contract(update='list')
def get_message(update):
    if 'message' in update:
        message = update['message']
    elif 'edited_message' in update:
        message = update['edited_message']
    else:
        print('Can\'t process! {}'.format(update))
    return message

@contract(chat='str')
def deps_text(task, chat, preceed=''):
    text = ''

    for i in range(len(task.dependencies.split(',')[:-1])):
        line = preceed
        query = db.session.query(Task).filter_by(id=int(task.dependencies.split(',')[:-1][i]), chat=chat)
        dep = query.one()

        icon = '\U0001F195'
        if dep.status == 'DOING':
            icon = '\U000023FA'
        elif dep.status == 'DONE':
            icon = '\U00002611'

        if i + 1 == len(task.dependencies.split(',')[:-1]):
            if dep.duedate == None:
                line += '└── [[{}]] {} | {} | {} | {}\n'.format(dep.id, icon, dep.name, dep.priority, dep.duedate)
            else:
                line += '└── [[{}]] {} | {} | {} | {}\n'.format(dep.id, icon, dep.name, dep.priority, dep.duedate.strftime("%d/%m/%Y"))

            line += deps_text(dep, chat, preceed + '    ')
        else:
            if dep.duedate == None:
                line += '├── [[{}]] {} | {} | {} | {}\n'.format(dep.id, icon, dep.name, dep.priority, dep.duedate)
            else:
                line += '├── [[{}]] {} | {} | {} | {}\n'.format(dep.id, icon, dep.name, dep.priority, dep.duedate.strftime("%d/%m/%Y"))
            line += deps_text(dep, chat, preceed + '│   ')

        text += line

    return text


@contract(msg='str', chat='str')
def create_task(msg, chat):

    task = Task(chat=chat, name=msg, status='TODO', dependencies='', parents='', priority='')
    db.session.add(task)
    db.session.commit()
    send_message("New task *TODO* [[{}]] {}".format(task.id, task.name), chat)
    return task

@contract(title='str', chat='str')
def make_github_issue(title, chat):
    '''Create an issue on github.com using the given parameters.'''
    # Our url to create issues via POST
    url = 'https://api.github.com/repos/%s/%s/issues' % (REPO_OWNER, REPO_NAME)
    # authenticated session to create the issue
    session = requests.session()
    session.auth = (get_user(), get_password())
    # Create our issue
    issue = {'title': title}
    # Add the issue to our repository
    r = session.post(url, json.dumps(issue))
    if r.status_code == 201:
        send_message('Successfully created Issue', chat)
        return True
    else:
        send_message('Could''t create Issue', chat)
        print ('Response:', r.content)
        return False

@contract(msg='str', chat='str')
def duplicate_task(msg, chat):
    if not msg.isdigit():
        send_message("You must inform the task id", chat)
    else:
        task_id = int(msg)
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        dtask = create_task(task.name, chat)

        for t in task.dependencies.split(',')[:-1]:
            qy = db.session.query(Task).filter_by(id=int(t), chat=chat)
            t = qy.one()
            t.parents += '{},'.format(dtask.id)

        db.session.commit()
        send_message("New task *TODO* [[{}]] {}".format(dtask.id, dtask.name), chat)

@contract(msg='str', chat='str')
def rename_task(msg, chat):
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]

    if not msg.isdigit():
        send_message("You must inform the task id", chat)
    else:
        task_id = int(msg)
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        if text == '':
            send_message("You want to modify task {}, but you didn't provide any new text".format(task_id), chat)
            return

        old_text = task.name
        task.name = text
        db.session.commit()
        send_message("Task {} redefined from {} to {}".format(task_id, old_text, text), chat)

@contract(msg='str', chat='str')
def delete_task(msg, chat):
    if not msg.isdigit():
        send_message("You must inform the task id", chat)
    else:
        task_id = int(msg)
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return
        for t in task.dependencies.split(',')[:-1]:
            qy = db.session.query(Task).filter_by(id=int(t), chat=chat)
            t = qy.one()
            t.parents = t.parents.replace('{},'.format(task.id), '')
        db.session.delete(task)
        db.session.commit()
        send_message("Task [[{}]] deleted".format(task_id), chat)

@contract(msg='str', chat='str', status='str')
def task_status(msg, chat, status):

    id_list = msg.split(" ")
    for id in id_list:
        if not id.isdigit():
            send_message("You must inform the task id", chat)
        else:
            task_id = int(id)
            query = db.session.query(Task).filter_by(id=task_id, chat=chat)
            try:
                task = query.one()
            except sqlalchemy.orm.exc.NoResultFound:
                send_message("_404_ Task {} not found x.x".format(task_id), chat)
                return
            task.status = status
            db.session.commit()
            send_message("*{}* task [[{}]] {}".format(task.status, task.id, task.name), chat)

@contract(chat='str')
def list_tasks(chat):
    message = ''

    message += '\U0001F4CB Task List\n'
    message += 'ID | STATUS | NAME | PRIORITY | DUEDATE\n'
    query = db.session.query(Task).filter_by(parents='', chat=chat).order_by(Task.id)
    for task in query.all():
        icon = '\U0001F195'
        if task.status == 'DOING':
            icon = '\U000023FA'
        elif task.status == 'DONE':
            icon = '\U00002611'

        if task.duedate == None:
            message += '[[{}]] |   {}   | {} | {}\n'.format(task.id, icon, task.name, task.priority)
        else:
            message += '[[{}]] |   {}   | {} | {} | {}\n'.format(task.id, icon, task.name, task.priority, task.duedate.strftime("%d/%m/%Y"))
        message += deps_text(task, chat)

    send_message(message, chat)
    message = ''

    message += '\U0001F4DD _Status_\n'
    query = db.session.query(Task).filter_by(status='TODO', chat=chat).order_by(Task.id)
    message += '\n\U0001F195 *TODO*\n'
    for task in query.all():
        message += '[[{}]] {}\n'.format(task.id, task.name)
    query = db.session.query(Task).filter_by(status='DOING', chat=chat).order_by(Task.id)
    message += '\n\U000023FA *DOING*\n'
    for task in query.all():
        message += '[[{}]] {}\n'.format(task.id, task.name)
    query = db.session.query(Task).filter_by(status='DONE', chat=chat).order_by(Task.id)
    message += '\n\U00002611 *DONE*\n'
    for task in query.all():
        message += '[[{}]] {}\n'.format(task.id, task.name)

    send_message(message, chat)

@contract(value='str')
def convert_to_integer(value):
    for i in range(len(value)):
        if value[i] == '':
            value[i] = 0
        else:
            value[i] = int(value[i])

@contract(msg='str', chat='str')
def task_dependencies(msg, chat):
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]

    if not msg.isdigit():
        send_message("You must inform the task id", chat)
    else:
        task_id = int(msg)
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)
        fTask = query.one()
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        if text == '':
            for i in task.dependencies.split(',')[:-1]:
                i = int(i)
                q = db.session.query(Task).filter_by(id=i, chat=chat)
                t = q.one()
                t.parents = t.parents.replace('{},'.format(task.id), '')

            task.dependencies = ''
            send_message("Dependencies removed from task {}".format(task_id), chat)
        else:
            for depid in text.split(' '):
                if not depid.isdigit():
                    send_message("All dependencies ids must be numeric, and not {}".format(depid), chat)
                else:
                    depid = int(depid)
                    query = db.session.query(Task).filter_by(id=depid, chat=chat)

                    firstTaskParent = fTask.parents.split(',')[0]
                    listOfParents = fTask.parents.split(',')

                    convert_to_integer(listOfParents)

                    if firstTaskParent != '':
                        for i in range(len(listOfParents)):
                            if listOfParents[i] == depid:
                                send_message("Invalid dependency", chat)
                            else:
                                pass
                    else:
                        try:
                            taskdep = query.one()
                            taskdep.parents += str(task.id) + ','
                        except sqlalchemy.orm.exc.NoResultFound:
                            send_message("_404_ Task {} not found x.x".format(depid), chat)
                            continue

                        deplist = task.dependencies.split(',')
                        if str(depid) not in deplist:
                            task.dependencies += str(depid) + ','

        db.session.commit()
        send_message("Task {} dependencies up to date".format(task_id), chat)


@contract(msg='str', chat='str')
def task_priority(msg, chat):
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]

    if not msg.isdigit():
        send_message("You must inform the task id", chat)
    else:
        task_id = int(msg)
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        if text == '':
            task.priority = ''
            send_message("_Cleared_ all priorities from task {}".format(task_id), chat)
        else:
            if text.lower() not in ['high', 'medium', 'low']:
                send_message("The priority *must be* one of the following: high, medium, low", chat)
            else:
                task.priority = text.lower()
                send_message("*Task {}* priority has priority *{}*".format(task_id, text.lower()), chat)
        db.session.commit()

@contract(msg='str', chat='str')
def task_duedate(msg, chat):
    text = ''
    if msg != '':
        if len(msg.split(' ', 1)) > 1:
            text = msg.split(' ', 1)[1]
        msg = msg.split(' ', 1)[0]

    if not msg.isdigit():
        send_message("You must inform the task id", chat)
    else:
        task_id = int(msg)
        query = db.session.query(Task).filter_by(id=task_id, chat=chat)
        try:
            task = query.one()
        except sqlalchemy.orm.exc.NoResultFound:
            send_message("_404_ Task {} not found x.x".format(task_id), chat)
            return

        if text == '':
            task.duedate = None
            send_message("_Cleared_ the duedate from task {}".format(task_id), chat)
        else:
            try:
                task.duedate = datetime.strptime(text, '%d/%m/%Y' )
                send_message("*Task {}*  has duedate *{}*".format(task_id, text), chat)
            except ValueError:
                send_message("The duedate *must be* in the following format: *'day/month/year'*", chat)
                return
        db.session.commit()


def handle_updates(updates):
    for update in updates["result"]:

        message = get_message(update)
        command = message["text"].split(" ", 1)[0]

        msg = ''
        if len(message["text"].split(" ", 1)) > 1:
            msg = message["text"].split(" ", 1)[1].strip()

        chat = message["chat"]["id"]

        print(command, msg, chat)

        if command == '/new':
            make_github_issue(msg, chat)
            create_task(msg, chat)

        elif command == '/rename':
            rename_task(msg, chat)

        elif command == '/duplicate':
            duplicate_task(msg, chat)

        elif command == '/delete':
            delete_task(msg, chat)

        elif command == '/todo':
            task_status(msg, chat, 'TODO')

        elif command == '/doing':
            task_status(msg, chat, 'DOING')

        elif command == '/done':
            task_status(msg, chat, 'DONE')

        elif command == '/list':
            list_tasks(chat)

        elif command == '/create_issue':
             make_github_issue(msg, chat)

        elif command == '/dependson':
            task_dependencies(msg, chat)
        elif command == '/priority':
            task_priority(msg, chat)
        elif command == '/duedate':
            task_duedate(msg, chat)
        elif command == '/start':
            send_message("Welcome! Here is a list of things you can do.", chat)
            send_message(HELP, chat)
        elif command == '/help':
            send_message("Here is a list of things you can do.", chat)
            send_message(HELP, chat)
        else:
            send_message("I'm sorry dave. I'm afraid I can't do that.", chat)


def main():
    last_update_id = None

    while True:
        print("Updates")
        updates = get_updates(last_update_id)

        if len(updates["result"]) > 0:
            last_update_id = get_last_update_id(updates) + 1
            handle_updates(updates)

        time.sleep(0.5)


if __name__ == '__main__':
    main()
