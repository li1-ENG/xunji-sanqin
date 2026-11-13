from email.message import EmailMessage
import smtplib

from ..config import (
    FEEDBACK_TO, SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USE_TLS, SMTP_USER,
)


def send_feedback_notification(feedback) -> None:
    if not SMTP_HOST or not FEEDBACK_TO:
        return
    message = EmailMessage()
    message['Subject'] = f'寻迹三秦反馈：{feedback.village_name or "未填写村落"}'
    message['From'] = SMTP_FROM or SMTP_USER
    message['To'] = FEEDBACK_TO
    message.set_content(
        '收到一条新的村落反馈\n\n'
        f'村落：{feedback.village_name or "未填写"}\n'
        f'城市：{feedback.city or "未填写"}\n'
        f'称呼：{feedback.name or "匿名"}\n'
        f'邮箱：{feedback.email or "未填写"}\n'
        f'类型：{feedback.category}\n\n'
        f'{feedback.message}\n'
    )
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as client:
            if SMTP_USE_TLS:
                client.starttls()
            if SMTP_USER:
                client.login(SMTP_USER, SMTP_PASSWORD)
            client.send_message(message)
    except Exception:
        # Email is a notification channel; the feedback remains stored in the database.
        return
