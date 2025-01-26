import asyncio
import hashlib
import os
import time
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import radiolist_dialog, message_dialog, yes_no_dialog, progress_dialog, input_dialog
import toml
import urllib.request as request

TITLE="Modpack Manager"
STYLE = Style.from_dict({
  "dialog": "bg:#000000",
  "dialog frame-label": "bg:#ffffff #000000",
  "dialog.body": "bg:#000000 #ffffff",
  "dialog shadow": "bg:#888888",
})

def hash_file_sha1(file):
  # BUF_SIZE is totally arbitrary, change for your app!
  BUF_SIZE = 65536  # lets read stuff in 64kb chunks!

  sha1 = hashlib.sha1()

  with open(file, 'rb') as f:
      while True:
          data = f.read(BUF_SIZE)
          if not data:
              break
          sha1.update(data)

  return sha1.hexdigest()


async def message(text):
  await message_dialog(
    title=TITLE,
    text=text,
    style=STYLE
  ).run_async()

async def confirm(text):
  return await yes_no_dialog(
    title=TITLE,
    text=text,
    style=STYLE,
  ).run_async()

async def main():
  while True:
    result = await radiolist_dialog(
      values=[
        ("download", "Download mods from index files"),
        ("package", "Package mods into a modpack"),
        ("chdir", "Change working directory"),
      ],
      title=TITLE,
      text=f"Current working directory: {os.getcwd()}\nPlease select a tool:",
      style=STYLE
    ).run_async()

    if result is None:
      return
  
    if result == "download":
      await download()
    elif result == "package":
      await package()
    elif result == "chdir":
      await chdir()

complete_log = ""
async def download():
  # Check if the mods/.index directory exists
  if not os.path.exists("mods/.index"):
    await message("The mods/.index directory does not exist.\nPlease make sure you're running this from the correct directory.")
    return True
  
  if not await confirm("This will delete all old .jar files in the mods directory\nAre you sure you want to continue?"):
    return False
  
  await progress_dialog(
    title=TITLE,
    text="Deleting .jar files in the mods directory and redownloading from index files...",
    run_callback=download_worker,
    style=STYLE
  ).run_async()

  global complete_log
  if complete_log:
    print(complete_log)
  complete_log = ""

  
  
  return False

def download_worker(set_percentage, log_text):
  def log(text):
    log_text(text + "\n")
    global complete_log
    complete_log += "\n" + text

  def ensure_key(dictionary, key):
    if not key in dictionary:
      log(f"Malformed index file: {file}")
      print(f"Malformed index file: {file}")
      return False
    return True
  
  index_dir = os.listdir("mods/.index")
  for file in index_dir:
    if not file.endswith(".toml"):
      index_dir.remove(file)

  set_percentage(0)

  keep = []
  for i, file in enumerate(index_dir):
    index = toml.load(f"mods/.index/{file}")
    # filename = 'abundant_atmosphere-1.19.2-1.0.2.jar'
    # name = 'Abundant Atmosphere'
    # [download]
    # hash = 'a70e90febcda5eec3381911beb4b3e448fd1b363'
    # hash-format = 'sha1'
    # mode = 'metadata:curseforge'
    # [update.curseforge]
    # file-id = 4083493
    # project-id = 682418

    if not ensure_key(index, "name") or not ensure_key(index, "filename") or not ensure_key(index, "download") or not ensure_key(index["download"], "mode") or not ensure_key(index["download"], "hash") or not ensure_key(index["download"], "hash-format"):
      continue

    if not index["download"]["mode"] == "metadata:curseforge":
      log(f"Unsupported download mode: {index['download']['mode']}")
      continue

    if not ensure_key(index, "update") or not ensure_key(index["update"], "curseforge") or not ensure_key(index["update"]["curseforge"], "file-id") or not ensure_key(index["update"]["curseforge"], "project-id"):
      continue

    # Check for hash
    if os.path.exists(f"mods/{index['filename']}"):
      if hash_file_sha1(f"mods/{index['filename']}") == index["download"]["hash"]:
        log(f"Skipping {index['name']} as it already exists and matches the hash")
        keep.append(index["filename"])
        set_percentage(int(i / len(index_dir) * 100))
        continue

    log(f"Downloading {index['name']} to {index['filename']}...")
    # https://mediafilez.forgecdn.net/files/6122/345/VestigesOfThePresent%201.20.1%20v.1.2.6.jar
    download_url = "https://mediafilez.forgecdn.net/files/{first}/{second}/{filename}".format(
      first=int(index["update"]["curseforge"]["file-id"] / 1000),
      second=index["update"]["curseforge"]["file-id"] % 1000,
      filename=index["filename"]
    )
    try:
      request.urlretrieve(download_url, f"mods/{index['filename']}")
    except Exception as e:
      log(f"Failed to download {index['name']}: {e}")
      continue
    keep.append(index["filename"])
    time.sleep(0.1)
    set_percentage(int(i / len(index_dir) * 100))

  for file in os.listdir("mods"):
    if not file.endswith(".jar") or file in keep:
      continue
    os.remove(f"mods/{file}")
    log(f"Removed {file}")

async def package():
  return False

async def chdir():
  new_dir = await input_dialog(
    title=TITLE,
    text=f"Current working directory: {os.getcwd()}\nEnter the new directory:",
    style=STYLE
  ).run_async()

  if new_dir is None:
    return
  
  if not os.path.exists(new_dir):
    await message(f"The directory \"{new_dir}\" does not exist.")
    return
  
  print(f"Changing directory to {new_dir}")
  os.chdir(new_dir)

if __name__ == "__main__":
  asyncio.run(main())
  input("Press Enter to exit...")