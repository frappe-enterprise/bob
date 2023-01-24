from fastapi import FastAPI, Response
from pydantic import BaseModel
from jinja2 import Environment,FileSystemLoader
import base64

app = FastAPI()

class Apps(BaseModel):
    project:str

def generate_apps(project) -> str:
    user = "athul"
    token= "gh-token"
    env = Environment(loader=FileSystemLoader("projects/"))
    template = env.get_template(f"{project}-apps.json")
    rendered = template.render(user=user,token=token)
    return base64.b64encode(rendered.encode()).decode()

@app.get("/")
async def hello():
    return {"msg":"hello"}

@app.get("/apps")
async def get_apps(project:str,response:Response):
    try:
        return generate_apps(project)
    except:
        response.status_code = 404
        return {"msg":"project not found"}

@app.post("/start")
async def start_build():
    pass
