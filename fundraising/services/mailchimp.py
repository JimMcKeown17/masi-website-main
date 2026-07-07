import os

import requests


class MailchimpAPIError(RuntimeError):
    """Raised when Mailchimp rejects a draft campaign request."""


def server_prefix_from_api_key(api_key):
    try:
        _, prefix = api_key.rsplit('-', 1)
    except (AttributeError, ValueError):
        raise ValueError("MAILCHIMP_API_KEY must include a server suffix like '-us21'")
    if not prefix:
        raise ValueError("MAILCHIMP_API_KEY server suffix is empty")
    return prefix


def api_base_url(api_key):
    prefix = server_prefix_from_api_key(api_key)
    return f"https://{prefix}.api.mailchimp.com/3.0"


def campaign_edit_url(prefix, web_id):
    return f"https://{prefix}.admin.mailchimp.com/campaigns/edit?id={web_id}"


def _mailchimp_detail(response):
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500]
    return payload.get('detail') or payload.get('title') or response.text[:500]


def _raise_for_status(response, action):
    if 200 <= response.status_code < 300:
        return
    detail = _mailchimp_detail(response)
    raise MailchimpAPIError(f"Mailchimp {action} failed ({response.status_code}): {detail}")


def create_draft_campaign(
    subject,
    html,
    audience_id,
    *,
    title,
    from_name="Masinyusane",
    reply_to="jim@masinyusane.org",
):
    api_key = os.getenv('MAILCHIMP_API_KEY')
    if not api_key:
        raise ValueError("MAILCHIMP_API_KEY is required")
    if not audience_id:
        raise ValueError("Mailchimp audience_id is required")

    prefix = server_prefix_from_api_key(api_key)
    base_url = api_base_url(api_key)
    auth = ("anystring", api_key)

    campaign_response = requests.post(
        f"{base_url}/campaigns",
        auth=auth,
        json={
            "type": "regular",
            "recipients": {"list_id": audience_id},
            "settings": {
                "subject_line": subject,
                "title": title,
                "from_name": from_name,
                "reply_to": reply_to,
            },
        },
        timeout=30,
    )
    _raise_for_status(campaign_response, "campaign creation")
    campaign = campaign_response.json()
    campaign_id = campaign['id']
    web_id = campaign['web_id']

    content_response = requests.put(
        f"{base_url}/campaigns/{campaign_id}/content",
        auth=auth,
        json={"html": html},
        timeout=30,
    )
    _raise_for_status(content_response, "content update")

    return {
        "campaign_id": campaign_id,
        "web_id": web_id,
        "edit_url": campaign_edit_url(prefix, web_id),
    }
