import asyncio
import glob
import hashlib
import json
import os
from pathlib import Path
import time

import pathspec
from custom_dialogs import multi_input_dialog, FieldDef, scrollable_text_dialog
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import radiolist_dialog, message_dialog, yes_no_dialog, progress_dialog, input_dialog, checkboxlist_dialog
import toml
import urllib.request as request

import zipfile

TITLE="Modpack Manager"
STYLE = Style.from_dict({
  "dialog": "bg:#000000",
  "dialog frame-label": "bg:#ffffff #000000",
  "dialog.body": "bg:#111111 #ffffff",
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
        ("package", "Package mods into a curseforge modpack"),
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

class CFManifest:
  def __init__(self):
    self.name = None
    self.version = None
    self.mc_version = None
    self.loader_id = None
    self.author = None

  def infer(self):
    self.infer_from_mmc()
    self.infer_from_instance()
    self.infer_from_pack()

  def infer_from_pack(self):
    if not os.path.exists("pack.toml"):
      return
    
    pack = toml.load("pack.toml")

    if "name" in pack:
      self.name = pack["name"]

    if "version" in pack:
      self.version = pack["version"]

    if "minecraft_version" in pack:
      self.mc_version = pack["minecraft_version"]

    if "forge_version" in pack:
      self.loader_id = f"forge-{pack['forge_version']}"

    if "author" in pack:
      self.author = pack["author"]

  def infer_from_mmc(self):
    if not os.path.exists("../mmc-pack.json"):
      return
    
    with open("../mmc-pack.json") as f:
      mmc_pack = json.load(f)
      
      if not "components" in mmc_pack:
        return
      
      for component in mmc_pack["components"]:
        if not "uid" in component:
          continue

        if component["uid"] == "net.minecraft":
          self.mc_version = component["version"]

        if component["uid"] == "net.minecraftforge":
          self.loader_id = f"forge-{component['version']}"

  def infer_from_instance(self):
    if not os.path.exists("../instance.cfg"):
      return
    
    with open("../instance.cfg") as f:
      file_contents = f.read()
      for line in file_contents.split("\n"):
        if line.startswith("ExportAuthor="):
          self.author = line[len("ExportAuthor="):]
        elif line.startswith("ManagedPackVersionName="):
          self.version = line[len("ManagedPackVersionName="):]
        elif line.startswith("ManagedPackName="):
          self.name = line[len("ManagedPackName="):]


  def to_dict(self):
    if not self.author or not self.version or not self.mc_version or not self.loader_id or not self.author:
      return None
    
    return {
      "author": self.author,
      "manifestType": "minecraftModpack",
      "manifestVersion": 1,
      "minecraft": {
        "modLoaders": [
          {
            "id": self.loader_id,
            "primary": True
          }
        ],
        "version": self.mc_version
      },
      "name": self.name,
      "overrides": "overrides",
      "version": self.version,
    }

async def package():
  if not os.path.exists("mods/.index"):
    await message("The mods/.index directory does not exist.\nPlease make sure you're running this from the correct directory.")
    return True
  
  manifest = CFManifest()
  manifest.infer()

  manifest_entered = await multi_input_dialog(
    title=TITLE,
    text="Please enter the following information:",
    fields=[
      FieldDef(key="name", name="Name", default=manifest.name),
      FieldDef(key="version", name="Version", default=manifest.version),
      FieldDef(key="author", name="Author", default=manifest.author),
      FieldDef(key="mc_version", name="Minecraft Version", default=manifest.mc_version),
      FieldDef(key="loader_id", name="Loader", default=manifest.loader_id),
    ],
    style=STYLE,
  ).run_async()

  if manifest_entered is None:
    return
  
  for key in manifest_entered:
    setattr(manifest, key, manifest_entered[key])

  if not manifest.to_dict():
    await message("Missing required fields for manifest.")
    return
  
  current_overrides = Path().glob('**/*')
  if Path(".packignore").exists():
    lines = Path(".packignore").read_text().splitlines()
    lines.extend([".git", "pack.toml", ".packignore"])

    spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)

    current_overrides = [
        str(file.relative_to(".")) for file in current_overrides if not spec.match_file(str(file))
    ]

  if not await scrollable_text_dialog(
    title=TITLE,
    text="These files are going to be added to the overrides (inferred from .packignore)\nPlease review them to be included in the modpack:",
    scrollable="\n".join(current_overrides),
    style=STYLE
  ).run_async():
    return

  def ensure_key(dictionary, key):
    return key in dictionary
  
  index_dir = os.listdir("mods/.index")
  mods = []

  exclude_mods = []
  if os.path.exists("pack.toml"):
    pack = toml.load("pack.toml")
    if ensure_key(pack, "exclude_mods"):
      exclude_mods = pack["exclude_mods"]

  for i, file in enumerate(index_dir):
    index = toml.load(f"mods/.index/{file}")
    if not ensure_key(index, "name") or not ensure_key(index, "download") or not ensure_key(index["download"], "mode"):
      continue

    if not index["download"]["mode"] == "metadata:curseforge":
      continue

    if not ensure_key(index, "update") or not ensure_key(index["update"], "curseforge") or not ensure_key(index["update"]["curseforge"], "file-id") or not ensure_key(index["update"]["curseforge"], "project-id"):
      continue

    mods.append({
      "name": index["name"],
      "projectID": index["update"]["curseforge"]["project-id"],
      "fileID": index["update"]["curseforge"]["file-id"]
    })

  mods = sorted(mods, key=lambda x: x["name"].lower())

  selected_mods = await checkboxlist_dialog(
    title=TITLE,
    text="Please select the mods to include in the modpack:",
    values=[(mod['projectID'], mod['name']) for mod in mods],
    default_values=[mod['projectID'] for mod in mods if not mod['projectID'] in exclude_mods],
    style=STYLE
  ).run_async()

  selected_mods = [mod for mod in mods if mod['projectID'] in selected_mods]

  if not selected_mods:
    if confirm("No mods selected. Continue?"):
      return
    
  manifest = manifest.to_dict()
  manifest["files"] = []

  for mod in selected_mods:
    manifest["files"].append({
      "fileID": int(mod["fileID"]),
      "projectID": int(mod["projectID"]),
      "required": True
    })

  zip_name = ""
  while zip_name.strip() == "":
    zip_name = await input_dialog(
      title=TITLE,
      text="Please enter the name of the zip file to save the modpack as:",
      default=f"{manifest['name']} {manifest['version']}.zip",
      style=STYLE
    ).run_async()

    if zip_name is None:
      return
    
    if not zip_name.endswith(".zip"):
      zip_name += ".zip"

    if zip_name.strip() == "":
      await message("Invalid zip name, please enter a valid name.")

  with zipfile.ZipFile(zip_name, 'w') as zipf:
    for file in current_overrides:
      zipf.write(file, arcname=f"overrides/{file}")

    zipf.writestr("manifest.json", json.dumps(manifest, indent=2))
  
  await message(f"Modpack saved as {zip_name}")
  
  
    

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