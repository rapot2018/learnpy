from fastapi import FastAPI

app = FastAPI()
@app.get("/hello")
def hello():
    return {"message": "Hello Ramesh"}


@app.get("/goodbye")
def goodbye():
    return {"message": "Goodbye Ramesh"}