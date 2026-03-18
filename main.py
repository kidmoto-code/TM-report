from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from report import UserData, Report   # импортируем твои классы

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
async def generate_report(numbers: str = Form(...)):
    # numbers — это текст из textarea
    input_data = numbers.split()

    # Очищаем предыдущие данные
    UserData.clear()
    
    # Добавляем данные как в телеграм-боте
    response = UserData.add_data(input_data)
    
    # Генерируем отчет
    Report()
    
    # Отправляем файл пользователю
    return FileResponse('report.docx', media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', filename='report.docx')
