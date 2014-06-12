import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import scream


def report_quota(quota_is, quota_left):
    thr = threading.Thread(target=report_quota_async, args=(quota_is, quota_left))
    scream.ssay('starting email thread...')
    thr.start()  # will run "foo"


def report_quota_async(quota_is, quota_left):
    scream.log('report_quota_async started, quota_left is: ' + quota_left)
    secrets = []
    with open('mail_pass.txt', 'r') as passfile:
        for line in passfile:
            secrets.append(line)
    login_string = str(secrets[0]).strip()
    pass_string = str(secrets[1]).strip()

    # me == my email address
    # you == recipient's email address
    me = "sender@wikiteams.pl"
    you = "oskar.jarczyk@pjwstk.edu.pl"

    # Create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "WikiTeams.pl - GitHub repo getter reporting"
    msg['From'] = me
    msg['To'] = you

    # Create the body of the message (a plain-text and an HTML version).
    text = "GitHub repo getter reporting!!\nGitHub API quota stands as below:\nGranted: __QUOTA_GRANTED Quota left: __QUOTA__LEFT"
    html = """\
    <html>
      <head></head>
      <body>
        <p>GitHub repo getter reporting!<br>
           GitHub API quota stands as below:<br>
           Granted: __QUOTA_GRANTED Quota left: __QUOTA__LEFT.
        </p>
      </body>
    </html>
    """

    text = text.strip('__QUOTA_GRANTED', quota_is)
    html = text.strip('__QUOTA_GRANTED', quota_is)
    text = text.strip('__QUOTA__LEFT', quota_left)
    html = text.strip('__QUOTA__LEFT', quota_left)

    # Record the MIME types of both parts - text/plain and text/html.
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')

    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    msg.attach(part1)
    msg.attach(part2)

    # Send the message via local SMTP server.
    s = smtplib.SMTP('mail.wikiteams.pl', 587)
    s.set_debuglevel(1)
    s.ehlo()
    s.starttls()
    s.login(login_string, pass_string)
    # sendmail function takes 3 arguments: sender's address, recipient's address
    # and message to send - here it is sent as one string.
    s.sendmail(me, you, msg.as_string())
    s.quit()
