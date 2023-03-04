# Bob the Builder

This is a small telegram bot which acts as a utility to build docker images on GitHub Actions without going to GitHub(and just from Telegram). 

It makes use of FastAPI for the bot server and uses a webhook based functioning. Some of the internals inside Bob are hardcoded which can be changed with a few changes(eg: Username, Action Repo and Projects folder).

# How to host it yourself

1. Create a new bot in Telegram
2. Use an online hosting service to Host the bot. You can find tons of tutorials online on how to host FastAPI apps.
  - You might need to provide a Bot Token and a GitHub API token with repo scope(if you aren't using private repositories, then give it anything) as environment variables `BOT_TOKEN` and `GH_TOKEN` respectively.
  - Also change the GitHub Username, Action Repo in the `main.py` file
3. Create a new telegram bot and set the webhook to `<your-hosted-instance-url>/webhook`
4. Next step is to create add projects. You can add projects in the `/projects` of this repo for examples
4. Next, you can talk to the bot and send a `/build` command and it will list all the projects which you can click on to build.


