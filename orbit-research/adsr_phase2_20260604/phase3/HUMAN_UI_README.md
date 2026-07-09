# 人评界面 — 启动说明

两个自带界面已生成(无需安装,离线可用):

- A/B 偏好: `phase3/human_ab/index.html`(80 对,160 个音频)
- 人声判定: `phase0/rater_packet/adjudication.html`(112 例,112 个音频)

## 方式一(推荐,在集群上起本地服务)
```bash
cd orbit-research/adsr_phase2_20260604/phase3/human_ab   # 或 phase0/rater_packet
python -m http.server 8731
```
评分员浏览器打开 `http://<本机或隧道>:8731/index.html`(判定包用 `adjudication.html`)。
用 Chrome / Firefox(支持 FLAC 播放)。

## 方式二(发给远端评分员)
`python scripts/build_human_ui.py --package` 会把真实音频拷进 `media/`,然后把整个
`phase3/human_ab/`(或 `phase0/rater_packet/`)目录打包发给评分员,本地双击 html 即可
(file:// 下用 Chrome/Firefox)。

## 使用与回收
- 右上角填**评分员缩写**;答题自动存浏览器(刷新不丢);完成后点底部「导出 CSV」。
- **2 位评分员**全评 + 自适应加裁(仅当主端点分歧、或有人标「拿不准」才上第三人);各自导出 CSV。
- A/B 的 `UNBLINDING_KEY.jsonl` 是 **PI 专属解盲钥匙,切勿给评分员**。
