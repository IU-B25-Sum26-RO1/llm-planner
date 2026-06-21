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
Если вы не пользовались гитхабом до этого или не привязывали SSH ключ, то стоит это сделать
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

## Установка зависимостей

Создание виртуального окружения и установка всех зависимостей:

```bash
uv sync
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

После добавления зависимости необходимо закоммитить:

* pyproject.toml
* uv.lock

---

## Обновление локальной копии

Перед началом работы:

```bash
git pull
uv sync
```

---

## Работа с ветками

Создать новую ветку:

```bash
git switch -c feature/<task-name>
```

Пример:

```bash
git switch -c feature/voice-control
```

После завершения работы:

```bash
git add .
git commit -m "Describe changes"
git push -u origin feature/<task-name>
```

Затем создать Pull Request в GitHub.

---

## Структура проекта

Описание директорий будет добавлено после формирования архитектуры проекта.




frfjfslkdfsld
fsdfskdf
fsdf
sdf
sd
fsd
fs
