# Документация архитектуры

На данном этапе проект имеет только часть для переработки голосового запроса в команду формата JSON, следственно файловая схема проекта выглядит так: 

```
app 
├── audio 
│   ├── decomposer.py 
│   ├── recognizer.py 
│   └── recorder.py 
├── main.py 
├── schemas.py 
├── sys_prompt_collector.py 
└── system_prompts
```
