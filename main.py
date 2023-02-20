from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from telegram.ext import CallbackContext, CommandHandler, Dispatcher, CallbackQueryHandler, ConversationHandler
from telegram import Update, Bot,InlineKeyboardButton, InlineKeyboardMarkup, parsemode
from telegram.parsemode import ParseMode as ps
from jinja2 import Environment,FileSystemLoader
import requests
import base64
import os

app = FastAPI()

BOT_TOKEN=os.getenv("BOT_TOKEN")
GH_TOKEN=os.getenv("GH_TOKEN")

class Image(BaseModel):
    project:str
    version:str
    frappe_version:str ="version-14"
    py_version:str = "3.10.5"
    nodejs_version:str = "16.18.0"
    apps_json:str 
    context:str = "git://github.com/frappe/frappe_docker"

def get_latest_erpnext_tag(version):
    res = requests.get("https://api.github.com/repos/frappe/erpnext/releases").json()
    for i in res:
        if i['target_commitish'] == version:
            return i['name']


def generate_apps(project) -> str:
    user = "athul"
    env = Environment(loader=FileSystemLoader("projects/"))
    template = env.get_template(f"{project}-apps.json")
    rendered = template.render(user=user,token=GH_TOKEN)
    return base64.b64encode(rendered.encode()).decode()

@app.get("/args")
def get_build_args(project,version="v14",frappe_version="version-14",py_version="3.10.5"):
    image = Image(project=project,version=version,frappe_version=frappe_version,py_version=py_version,apps_json=generate_apps(project))
    return image

@app.get("/")
async def hello():
    return {"msg":"hello"}

@app.get("/rmdir")
async def rmdir():
    print(os.listdir("."))
    print(os.path.abspath("projects"))
    # import shutil
    # shutil.rmtree("/var/task/projects")
    print(os.listdir("projects/"))
    # import glob
    # files = glob.glob("projects/*")
    # for f in files:
    #     os.remove(f)
    return os.listdir(".")

@app.get("/apps")
async def get_apps(project:str,response:Response):
    try:
        return generate_apps(project)
    except:
        response.status_code = 404
        return {"msg":"project not found"}

@app.post("/build")
def start_build(image:Image)->requests.Response:
    image.apps_json = generate_apps(image.project)
    headers= {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {GH_TOKEN}',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/x-www-form-urlencoded',
            } 
    data = f'{{"ref":"main","inputs":{{"image":"{image.project}","version":"{image.version}","frappe-version":"{image.frappe_version}","py-version":"{image.py_version}","nodejs-version":"{image.nodejs_version}","apps-json-base64":"{image.apps_json}","context":"{image.context}","cache":"true","frappe-repo":"https://github.com/frappe/frappe"}}}}'
    response = requests.post(
                'https://api.github.com/repos/frappe-enterprise/bob/actions/workflows/build.yml/dispatches',
                    headers=headers,
                        data=data,
            )
    print(response.text)
    return response

@app.get("/projects")
def return_projects():
    return get_projects()

def get_projects():
    import glob
    files = glob.glob("./projects/*.json")
    return [x.split("/")[2].split("-")[0] for x in files]

def generate_inline_buttons(args:bool=False):
    projects = get_projects()
    keyboard = []
    keyboard_items = []
    # if args:
    #     for key in **Image:
    #         pass
    for project in projects:
        keyboard_items.append(InlineKeyboardButton(project,callback_data=project))
    keyboard.append(keyboard_items)
    keyboard.append([InlineKeyboardButton("Change Build Args", callback_data="change")])
    return keyboard

def send_build_request(upd: Update,_:CallbackContext):
    reply_markup = InlineKeyboardMarkup(generate_inline_buttons())
    upd.message.reply_text("Please choose from the list of apps.json file for the client:", reply_markup=reply_markup)


# def change(upd:Update,ctx:CallbackContext):
#     query = upd.callback_query
#     query.answer()
#     kb = generate_inline_buttons(args=True)


def build_button(upd:Update, ctx:CallbackContext):
    query = upd.callback_query
    query.answer()
    ctx.bot.send_message(ctx._chat_id_and_data[0],text=generate_apps(query.data))
    image = get_build_args(query.data)
    if query.data == "iftas":
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
    # regsiter_handler = ConversationHandler(
    #         entry_points=[CommandHandler("build",send_build_request)],
    #
    #         )
    return dp

disp = get_dispatcher()

@app.post("/webhook")
async def handle_webhooks(req:Request):
    data = await req.json()
    update = Update.de_json(data, disp.bot)
    disp.process_update(update)

