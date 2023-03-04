from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from telegram.ext import CallbackContext, CommandHandler, Dispatcher, CallbackQueryHandler, ConversationHandler
from telegram import Update, Bot,InlineKeyboardButton, InlineKeyboardMarkup, parsemode
from telegram.parsemode import ParseMode as ps
from jinja2 import Environment,FileSystemLoader,meta
import requests
import json
import base64
import os

app = FastAPI()

BOT_TOKEN=os.getenv("BOT_TOKEN")
GH_TOKEN=os.getenv("GH_TOKEN")


class Image(BaseModel):
    project:str
    version:str = "v14"
    frappe_version:str ="version-14"
    py_version:str = "3.10.5"
    nodejs_version:str = "16.18.0"
    apps_json:str 
    context:str = "git://github.com/frappe/frappe_docker"

def get_latest_erpnext_tag(version):
    """
    Maybe useful in the future``
    """
    res = requests.get("https://api.github.com/repos/frappe/erpnext/releases").json()
    for i in res:
        if i['target_commitish'] == version:
            return i['name']

def get_latest_tag(repo:str) -> str|None:
    """
    Get's latest tag from GitHub
    """
    res = requests.get(f"https://api.github.com/repos/{repo}/releases")
    if res.ok:
        return res.json()[0]['name']

@app.get("/repos")
def get_repo(project):
    """
    Get's the name of the repo where the tag needs to be latest.

    Returns a tag_name:tag_value dict for all repos which require latest tags
    """
    repos = {} 
    with open(f"projects/{project}-apps.json") as f:
        apps=json.load(f)
    for app in apps:
        if "{{" in app['branch']:
              repo = app["url"].split("://")[1].split("/",1)[1]
              tag = get_latest_tag(repo)
              repos[app["branch"].replace("{{","").replace("}}","")] = tag
    return repos

@app.get("/render")
def generate_apps(project) -> str:
    """
    Render the template with the token and variables if those are required
    
    """
    user = "athul"
    env = Environment(loader=FileSystemLoader("projects/"))
    template = env.get_template(f"{project}-apps.json")
    render_tags = get_repo(project)
    context = {"user":user,"token":GH_TOKEN,**render_tags}
    rendered = template.render(context)
    return base64.b64encode(rendered.encode()).decode()

@app.get("/args")
def get_build_args(project:str):
    """
    Get Arguments for build for using Manually
    """
    image = Image(project=project,apps_json=generate_apps(project))
    if "v13" in project:
        image.version = "v13"
        image.frappe_version ="version-13"
        image.py_version = "3.9"
        image.nodejs_version = "14.20.0"

    return image

 
@app.get("/")
async def hello():
    return {"msg":"hello"}

@app.get("/apps")
async def get_apps(project:str,response:Response):
    """
    Get apps.json as a base64 encoded form
    """
    try:
        return generate_apps(project)
    except:
        response.status_code = 404
        return {"msg":"project not found"}

@app.post("/build")
def start_build(image:Image)->requests.Response:
    """
    Handles everything build related from GitHub
    """
    image.apps_json = generate_apps(image.project)
    headers= {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {GH_TOKEN}',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/x-www-form-urlencoded',
            } 
    data = f'{{"ref":"main","inputs":{{"image":"{image.project}","version":"{image.version}","frappe-version":"{image.frappe_version}","py-version":"{image.py_version}","nodejs-version":"{image.nodejs_version}","apps-json-base64":"{image.apps_json}","context":"{image.context}","cache":"false","frappe-repo":"https://github.com/frappe/frappe"}}}}'
    response = requests.post(
                'https://api.github.com/repos/frappe-enterprise/bob/actions/workflows/build.yml/dispatches',
                    headers=headers,
                        data=data,
            )
    return response


@app.get("/projects")
def get_projects():
    """
    Return the dict of projects from the projects folder
    """
    import glob
    files = glob.glob("./projects/*.json")
    return [x.split("/")[2].split("-")[0] for x in files]

def generate_inline_buttons():
    """
    Generate Inline Buttons for the Telegram Keyboard
    """
    projects = get_projects()
    keyboard = []
    for project in projects:
        keyboard.append([InlineKeyboardButton(project,callback_data=project)])
    return keyboard

def send_build_request(upd: Update,_:CallbackContext):
    """
    Send Message when /build is called
    """
    reply_markup = InlineKeyboardMarkup(generate_inline_buttons())
    upd.message.reply_text("Please choose from the list of apps.json file for the client:", reply_markup=reply_markup)

def build_button(upd:Update, ctx:CallbackContext):
    """
    Handles the callback from Telegram and processes GH builds

    """
    query = upd.callback_query
    query.answer()
    image = get_build_args(query.data)
    if query.data == "iftas": #Change Context due to additional iftas changes
        image.context = "git://github.com/frappe-enterprise/frappe_docker.git#refs/heads/iftas"
    resp = start_build(image=image)
    ctx.bot.send_message(ctx._chat_id_and_data[0],text=f"Build Args:\n ```{image.dict()}```",parse_mode=ps.MARKDOWN)
    if resp.status_code == 204:
        query.edit_message_text(text=f"Build started for {query.data} \nFind logs at https://github.com/frappe-enterprise/bob/actions")
    else:
        query.edit_message_text(text=f"Build failed to start for {query.data}, please refer to {resp.json()}",parse_mode=ps.HTML)

def get_dispatcher():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher(bot=bot, update_queue=None, use_context=True)
    dp.add_handler(CommandHandler("build",send_build_request))
    dp.add_handler(CallbackQueryHandler(build_button))
    return dp

disp = get_dispatcher()

@app.post("/webhook")
async def handle_webhooks(req:Request):
    """
    Handles the webhook from Telegram
    """
    data = await req.json()
    update = Update.de_json(data, disp.bot)
    disp.process_update(update)

