import sys
import os
import subprocess
import argparse
from datetime import datetime
import shutil

from main_continual import str_to_dict

# -----------------------------
# 引数のパース
# -----------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--script", type=str, required=True)  # 実行するスクリプト
parser.add_argument("--mode", type=str, default="normal") # normal / slurm
parser.add_argument("--experiment_dir", type=str, default=None)  # 実験ディレクトリ名
parser.add_argument("--base_experiment_dir", type=str, default="./experiments")  # 基本パス
parser.add_argument("--gpu", type=str, default="v100-16g")
parser.add_argument("--num_gpus", type=int, default=2)
parser.add_argument("--hours", type=int, default=20)
parser.add_argument("--requeue", type=int, default=0)
args = parser.parse_args()

# -----------------------------
# スクリプトの読み込み
# -----------------------------
if os.path.exists(args.script):
    with open(args.script) as f:
        # 行末のバックスラッシュや空白を除去してリスト化
        command = [line.strip().strip("\\").strip() for line in f.readlines()]
else:
    print(f"{args.script} does not exist.")
    exit()

# checkpoint_dir は launcher 側で自動追加するので、スクリプト内では指定しない
assert (
    "--checkpoint_dir" not in command
), "Please remove the --checkpoint_dir argument, it will be added automatically"

# -----------------------------
# スクリプト内の引数を辞書化
# -----------------------------
command_args = str_to_dict(" ".join(command).split(" ")[2:])

# -----------------------------
# experiment_dir の設定
# -----------------------------
if args.experiment_dir is None:
    # 指定がなければスクリプト名または日時を利用
    args.experiment_dir = command_args.get('--name', datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))

full_experiment_dir = os.path.join(args.base_experiment_dir, args.experiment_dir)

# -----------------------------
# 既存ディレクトリがあれば再利用 (Drive 上のチェックポイントを使う)
# -----------------------------
if os.path.exists(full_experiment_dir):
    print(f"Resuming experiment from existing directory: {full_experiment_dir}")
else:
    os.makedirs(full_experiment_dir, exist_ok=True)
    print(f"Created new experiment directory: {full_experiment_dir}")

# -----------------------------
# スクリプトをコピーして再現性確保
# -----------------------------
shutil.copy(args.script, full_experiment_dir)

# -----------------------------
# checkpoint_dir を自動追加
# -----------------------------
command.extend(["--checkpoint_dir", full_experiment_dir])
command = " ".join(command)
print("Running command:")
print(command)

# -----------------------------
# 実行
# -----------------------------
if args.mode == "normal":
    # ローカル実行
    p = subprocess.Popen(command, shell=True, stdout=sys.stdout, stderr=sys.stdout)
    p.wait()

elif args.mode == "slurm":
    # SLURM 実行用
    # QoS 推定
    if 0 <= args.hours <= 2:
        qos = "qos_gpu-dev"
    elif args.hours <= 20:
        qos = "qos_gpu-t3"
    elif args.hours <= 100:
        qos = "qos_gpu-t4"

    # コマンドを書き出し
    command_path = os.path.join(full_experiment_dir, "command.sh")
    with open(command_path, "w") as f:
        f.write(command)

    # sbatch で実行
    p = subprocess.Popen(f"sbatch {command_path}", shell=True, stdout=sys.stdout, stderr=sys.stdout)
    p.wait()
