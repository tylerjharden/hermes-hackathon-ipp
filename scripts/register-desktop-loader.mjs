import { register } from "node:module"
import { pathToFileURL } from "node:url"

register("./desktop_loader.mjs", import.meta.url)
