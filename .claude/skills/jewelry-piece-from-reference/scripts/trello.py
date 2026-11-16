"""Чтение заказов из Trello (только GET). Ключ и токен — из личного файла настроек (строки
«API Key: ...» и «Token: ...»), путь передаётся в --config; в репозитории их нет.

  python3 trello.py --config ПУТЬ boards
  python3 trello.py --config ПУТЬ lists ДОСКА            # ДОСКА — id или часть названия
  python3 trello.py --config ПУТЬ cards ДОСКА СПИСОК      # СПИСОК — название колонки
  python3 trello.py --config ПУТЬ card ID [--download ПАПКА]   # описание и вложения-картинки
"""
import argparse, json, os, re, sys, urllib.parse, urllib.request


def client(config):
    text = open(os.path.expanduser(config)).read()
    key = re.search(r"API Key:\W*(\w+)", text).group(1)
    token = re.search(r"Token:\W*(\w+)", text).group(1)

    def get(path, **q):
        q.update(key=key, token=token)
        with urllib.request.urlopen("https://api.trello.com/1/" + path + "?" + urllib.parse.urlencode(q)) as r:
            return json.load(r)

    def download(url, dst):
        head = {"Authorization": 'OAuth oauth_consumer_key="%s", oauth_token="%s"' % (key, token)}
        with urllib.request.urlopen(urllib.request.Request(url, headers=head)) as r, open(dst, "wb") as f:
            f.write(r.read())
    return get, download


def board_id(get, name):
    boards = get("members/me/boards", fields="name", filter="open")
    hit = [b for b in boards if b["id"] == name or name.lower() in b["name"].lower()]
    if len(hit) != 1:
        sys.exit("board '%s': %d matches (%s)" % (name, len(hit), ", ".join(b["name"] for b in boards)))
    return hit[0]["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("what", choices=["boards", "lists", "cards", "card"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--download")
    a = ap.parse_args()
    get, download = client(a.config)
    if a.what == "boards":
        for b in get("members/me/boards", fields="name", filter="open"):
            print(b["id"], b["name"])
    elif a.what == "lists":
        for l in get("boards/%s/lists" % board_id(get, a.args[0]), fields="name"):
            print(l["id"], l["name"])
    elif a.what == "cards":
        lists = get("boards/%s/lists" % board_id(get, a.args[0]), fields="name")
        lid = next(l["id"] for l in lists if l["name"].strip().lower() == a.args[1].strip().lower())
        for c in get("lists/%s/cards" % lid, fields="name,badges"):
            print(c["id"], "att %d |" % c["badges"]["attachments"], c["name"])
    else:
        c = get("cards/" + a.args[0], fields="name,desc", attachments="true")
        print(c["name"], "\n", c["desc"], sep="")
        for i, at in enumerate(c["attachments"]):
            print("att", i, at["name"], at.get("mimeType"), at["bytes"])
            if a.download and at["isUpload"] and (at.get("mimeType") or "").startswith("image"):
                os.makedirs(a.download, exist_ok=True)
                download(at["url"], os.path.join(a.download, "%d%s" % (i, os.path.splitext(at["name"])[1] or ".jpg")))


if __name__ == "__main__":
    main()
