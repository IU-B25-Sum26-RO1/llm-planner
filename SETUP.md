# SETUP

## Требования

* Git
* Python 3.13 (3.13.5)
* uv (https://docs.astral.sh/uv/getting-started/installation/#installing-uv)

Проверить установку:

```bash
python --version
uv --version
git --version
```
---
Если вы не пользовались гитхабом до этого или не привязывали SSH ключ, то стоит это сделать.

Инструкция: https://docs.github.com/en/authentication/connecting-to-github-with-ssh

---

## Клонирование репозитория

Перейдите в директорию с проектами (или создайте, если таковой нет)
```bash
mkdir ~/Projects
cd ~/Projects
```
Там клонируйте репозиторий
```bash
git clone git@github.com:IU-B25-Sum26-RO1/llm-planner.git
cd <repository>
```

---

## Установка пакетов

Создание виртуального окружения и установка всех зависимостей:

```bash
uv sync
# Должно появиться новое виртуальное окружение
```

---

## Активация окружения

### Linux / macOS

```bash
source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
.venv\Scripts\Activate.ps1
```

### Windows (Git Bash)

```bash
source .venv/Scripts/activate
```

---

## Добавление новой зависимости

```bash
uv add <package>
```

Пример:

```bash
uv add fastapi
```

После добавления зависимости необходимо коммитить:

* pyproject.toml
* uv.lock

---

## Обновление локальной копии

Перед началом работы:

```bash
git switch main # переключаемся на main-ветку (локальную)
git pull origin main # подтягиваем изменения из origin (Github) в main (локально)
uv sync # синхронизируемся по pyproject.toml и uv.lock
```

---

## Работа с ветками

Создать новую ветку:

Вообще любые изменения проводить в новой ветке и пушить в неё же. Потом, после того, как вы закончили работу, запросить Pull Request.   

```bash
git switch -c feature/<task-name>
```

Пример:

```bash
git switch -c feature/voice-control
```

После завершения работы:

```bash
git status # Какие файлы претерпели изменения
```

```bash
git add . # Все измененные файлы
# git add <path_to_file> - добавление файлов по одному
git commit -m "Describe changes" 
git push -u origin feature/<task-name>
```

Затем создать Pull Request в GitHub.

---

## Структура проекта

<!-- TODO: После согласования добавить структуру -->
