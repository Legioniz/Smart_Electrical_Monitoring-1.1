#!/usr/bin/env python3
"""Opt in to a locally installed Ollama model after verifying its manifest hash."""
from __future__ import annotations
import argparse, hashlib, os, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sme.services.narrative import ollama_manifest_digest

def read_env():
    values = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                k,v=line.split("=",1); values[k.strip()] = v.strip().strip('"').strip("'")
    return values

def write_env(values):
    path=ROOT/".env"; lines=path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen=set(); output=[]
    for line in lines:
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key=line.split("=",1)[0].strip()
            if key in values: output.append(f"{key}={values[key]}"); seen.add(key); continue
        output.append(line)
    for key,value in values.items():
        if key not in seen: output.append(f"{key}={value}")
    path.write_text("\n".join(output).rstrip()+"\n",encoding="utf-8")
    try: path.chmod(0o600)
    except OSError: pass

def main():
    parser=argparse.ArgumentParser(description="Configure an optional local Ollama model for energy story and suggestions")
    parser.add_argument("--model", help="installed Ollama model name, e.g. llama3.2:3b")
    parser.add_argument("--models-dir", help="Ollama models directory (defaults to ~/.ollama/models or OLLAMA_MODELS_DIR)")
    args=parser.parse_args()
    ollama=shutil.which("ollama")
    if not ollama:
        print("Ollama CLI was not found. Install Ollama and pull a local model first; this script does not download large models automatically.")
        return 2
    values=read_env()
    models_dir=Path(args.models_dir or values.get("OLLAMA_MODELS_DIR") or os.getenv("OLLAMA_MODELS_DIR") or os.getenv("OLLAMA_MODELS") or Path.home()/".ollama"/"models").expanduser()
    model=args.model
    if not model:
        result=subprocess.run([ollama,"list"],capture_output=True,text=True,timeout=20)
        if result.returncode:
            print(result.stderr or "Could not query Ollama."); return 2
        names=[]
        for line in result.stdout.splitlines()[1:]:
            parts=line.split()
            if parts and re.fullmatch(r"[A-Za-z0-9._:/-]+",parts[0]): names.append(parts[0])
        if not names:
            print("No local models are installed. Run `ollama pull <model>` then rerun this script."); return 2
        print("Installed local models:")
        for index,name in enumerate(names,1): print(f"  {index}. {name}")
        choice=input("Choose a model number or type its exact name: ").strip()
        model=names[int(choice)-1] if choice.isdigit() and 1 <= int(choice) <= len(names) else choice
    digest=ollama_manifest_digest(model,models_dir)
    if not digest:
        print(f"Could not find a standard local Ollama manifest for {model!r} under {models_dir}.")
        print("Confirm the model is installed locally and set OLLAMA_MODELS_DIR if Ollama stores models elsewhere.")
        return 2
    values.update({"LOCAL_LLM_ENABLED":"true","OLLAMA_MODEL":model,"OLLAMA_MODEL_SHA256":digest,"OLLAMA_MODELS_DIR":str(models_dir.resolve()),"OLLAMA_URL":values.get("OLLAMA_URL","http://127.0.0.1:11434/api/generate")})
    write_env(values)
    print(f"Enabled local Ollama model: {model}")
    print(f"Verified manifest SHA-256: {digest}")
    print("Restart the app. Model output will be validated against computed facts; deterministic templates remain the fallback.")
    return 0
if __name__=="__main__": raise SystemExit(main())
