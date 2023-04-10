import os
import re
import sys
import json
import shutil
from datetime import datetime

sys.path.append(os.path.dirname(__file__))


import chardet

import anki
from aqt import mw
from aqt.utils import showInfo
from aqt.qt import *
from PyQt5 import QtWidgets


def get_folder_paths(note, config, obsidian_attachment_folder):
    deck = mw.col.decks.name(note.cards()[0].did)
    folder_path = [
        re.sub('[\\\/:*?"<>|]', "-", dir.strip()) for dir in deck.split("::")
    ]
    folder_path = os.path.join(config["obsidianPath"], *folder_path)
    os.makedirs(folder_path, exist_ok=True)
    if obsidian_attachment_folder.startswith("/"):
        attachment_folder_path = config["obsidianPath"]
    elif obsidian_attachment_folder.startswith("./"):
        attachment_folder_path = os.path.join(
            folder_path, obsidian_attachment_folder[2:]
        )
    else:
        attachment_folder_path = os.path.join(
            config["obsidianPath"], obsidian_attachment_folder
        )
    return folder_path, attachment_folder_path


def sync_to_obsidian(browser):
    config = mw.addonManager.getConfig(__name__)
    if config["headingLevel"] not in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        showInfo(
            "headingLevel must be one of h1, h2, h3, h4, h5, h6. Please change in setting."
        )
    heading_level = "#" * int(config["headingLevel"][-1])
    if config["obsidianPath"] == "":
        showInfo("Obsidian path is empty, please add it in setting.")
    else:
        app_json = open(
            os.path.join(config["obsidianPath"], ".obsidian", "app.json"), "rb"
        ).read()
        detect_encoding = chardet.detect(app_json)

        obsidian_attachment_folder = json.loads(
            app_json.decode(encoding=detect_encoding["encoding"])
        )["attachmentFolderPath"]

        notes = [mw.col.get_note(note_id) for note_id in browser.selectedNotes()]

        for note in notes:
            field_names = note.keys()
            folder_path, attachment_folder_path = get_folder_paths(
                note, config, obsidian_attachment_folder
            )
            file_name = re.compile(r"<[^>]+>", re.S).sub("", note.fields[0])
            media_list_front = mw.col.media.files_in_str(note.mid, note.fields[0])
            if os.path.exists(os.path.join(folder_path, file_name + ".md")):
                continue
            with open(
                os.path.join(folder_path, file_name + ".md"),
                "w",
                encoding=detect_encoding["encoding"],
            ) as f:
                f.write(f"---\nmid: {note.mid}\nnid: {note.id}\ntags: [")
                if len(note.tags) > 0:
                    f.write(f"{note.tags[0]}")
                    for tag in note.tags[1:]:
                        f.write("," + tag)
                f.write("]\ndate: " + str(datetime.fromtimestamp(note.mod)) + "\n---\n")

                if len(media_list_front) > 0:
                    f.write(f"\nMedia files in the first field of note.\n")
                    for media in media_list_front:
                        print(os.path.join(mw.col.media.dir(), media))
                        shutil.copy2(
                            os.path.join(mw.col.media.dir(), media),
                            os.path.join(attachment_folder_path, media),
                        )
                        f.write(f"\n![[{media}]]\n")

                for i, (field_name, field) in enumerate(
                    zip(field_names[1:], note.fields[1:])
                ):
                    media_list = mw.col.media.files_in_str(note.mid, field)
                    if i > 0:
                        f.write(f"\n{heading_level} {field_name}\n")
                    if len(media_list) == 0:
                        f.write(f"\n{field}\n")
                    else:
                        media_texts = re.findall(
                            re.compile(r"<img [^>]+>|\[sound:.*\]"), field
                        )
                        field_list = []
                        for i, media_text in enumerate(media_texts):
                            field_list += field.split(media_text)
                            field = field_list[-1]
                            for media_name in media_list:
                                if media_name in media_text:
                                    if i < len(media_texts) - 1:
                                        field_list[-1] = media_name
                                    else:
                                        field_list.insert(-1, media_name)

                        for field in field_list:
                            if field in media_list:
                                shutil.copy2(
                                    os.path.join(mw.col.media.dir(), field),
                                    os.path.join(attachment_folder_path, field),
                                )
                                f.write(f"\n![[{field}]]\n")
                            else:
                                field = re.compile(r"<[^>]+>", re.S).sub("", field)
                                f.write(f"\n{field}\n")


def on_setup_menus(browser):
    menu = QtWidgets.QMenu("Sync to Obsidian", browser.form.menubar)
    browser.form.menubar.addMenu(menu)

    def sync():
        sync_to_obsidian(browser)

    action = menu.addAction("Sync to Obsidian")
    action.triggered.connect(sync)


anki.hooks.addHook(
    "browser.setupMenus",
    on_setup_menus,
)
