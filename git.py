import json
import requests

# Authentication for user filing issue (must have read/write access to
# repository to add issue to)
USERNAME = 'bot'
PASSWORD = '123456'

# The repository to add this issue to
REPO_OWNER = 'TecProg-20181'
REPO_NAME = 'T--jarvis_task_bot'

def make_github_issue(title, labels=['create_by_bot'] ):
    '''Create an issue on github.com using the given parameters.'''
    # Our url to create issues via POST
    url = 'https://api.github.com/repos/%s/%s/issues' % (REPO_OWNER, REPO_NAME)
    # authenticated session to create the issue
    session = requests.session()
    session.auth = (USERNAME, PASSWORD)
    # Create our issue
    issue = {'title': title,
             'labels': labels}
    # Add the issue to our repository
    r = session.post(url, json.dumps(issue))
    if r.status_code == 201:
        print('Successfully created Issue')
        return True
    else:
        print ('Could''t create Issue')
        print ('Response:', r.content)
        return False