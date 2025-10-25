#!/usr/bin/env pwsh  # 指定脚本默认由 PowerShell Core 运行，便于跨平台执行。
$ErrorActionPreference = 'Stop'  # 当出现错误时立即终止脚本，避免忽略关键失败。
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'  # 统一命令输出文件的编码为 UTF-8。
$ScriptDir = Split-Path -LiteralPath $MyInvocation.MyCommand.Path -Parent  # 解析脚本所在目录的绝对路径。
$RepoRoot = Resolve-Path (Join-Path $ScriptDir '..')  # 计算仓库根目录，方便引用项目文件。
$DefaultCacheDir = Join-Path $RepoRoot '.cache'  # 设置缓存目录默认值。
$DefaultVenvDir = Join-Path $RepoRoot '.venv'  # 设置虚拟环境目录默认值。
$CheckOnly = 'false'  # 默认执行真实安装而非仅检查。
$PythonPath = ''  # 初始化 Python 可执行文件路径，由脚本自动探测。
$UseSystemFfmpeg = 'true'  # 默认优先使用系统级 ffmpeg/ffprobe。
$CacheDir = $DefaultCacheDir  # 当前缓存目录，初始为默认值。
$VenvDir = $DefaultVenvDir  # 当前虚拟环境目录，初始为默认值。
$ModelBackend = 'faster-whisper'  # 模型下载后端默认 faster-whisper。
$ModelName = 'medium'  # 模型规格默认 medium。
$DefaultModelsDir = Join-Path $HOME '.cache/asrprogram/models'  # 默认模型缓存目录。
$ModelsDir = $DefaultModelsDir  # 当前模型缓存目录，初始为默认值。
$ExtraIndexUrl = ''  # 允许用户指定额外的 pip 索引。
$RequirementsFile = Join-Path $RepoRoot 'requirements.txt'  # 指定依赖清单文件路径。
function Show-Help {  # 定义函数输出脚本帮助信息。
    Write-Host '用法：pwsh -File scripts/setup.ps1 [参数]'  # 打印用法示例。
    Write-Host '  -check-only true|false        是否仅执行环境体检，默认 false。'  # 说明 check-only 参数。
    Write-Host '  -python <path>                指定 Python 解释器路径。'  # 说明 python 参数。
    Write-Host '  -use-system-ffmpeg true|false 是否优先使用系统 ffmpeg/ffprobe，默认 true。'  # 说明 ffmpeg 策略。
    Write-Host '  -cache-dir <path>             指定缓存目录，默认为仓库下 .cache。'  # 说明缓存目录。
    Write-Host '  -venv-dir <path>              指定虚拟环境目录，默认为仓库下 .venv。'  # 说明虚拟环境目录。
    Write-Host '  -backend <name>               指定模型下载后端，默认 faster-whisper。'  # 说明模型后端参数。
    Write-Host '  -model <name>                 指定模型规格，默认 medium。'  # 说明模型规格参数。
    Write-Host '  -models-dir <path>            指定模型缓存目录，默认 ~/.cache/asrprogram/models。'  # 说明模型目录参数。
    Write-Host '  -extra-index-url <url>        为 pip 安装追加索引源。'  # 说明额外索引参数。
    Write-Host '  -help                         查看帮助信息并退出。'  # 说明帮助参数。
}  # 结束帮助函数定义。
for ($i = 0; $i -lt $args.Length; $i++) {  # 使用循环逐项解析用户输入参数。
    $current = $args[$i]  # 读取当前参数名。
    switch ($current) {  # 根据参数名称匹配不同分支。
        '-check-only' {  # 解析 -check-only 参数。
            if ($i + 1 -lt $args.Length) {  # 确保存在对应的值。
                $CheckOnly = $args[$i + 1]  # 记录布尔值。
                $i++  # 跳过已处理的值。
            }
        }
        '-python' {  # 解析 -python 参数。
            if ($i + 1 -lt $args.Length) {  # 校验值是否存在。
                $PythonPath = $args[$i + 1]  # 记录 Python 路径。
                $i++  # 跳过该值。
            }
        }
        '-use-system-ffmpeg' {  # 解析 -use-system-ffmpeg 参数。
            if ($i + 1 -lt $args.Length) {  # 校验值是否存在。
                $UseSystemFfmpeg = $args[$i + 1]  # 记录策略。
                $i++  # 跳过值。
            }
        }
        '-cache-dir' {  # 解析 -cache-dir 参数。
            if ($i + 1 -lt $args.Length) {  # 校验值是否存在。
                $CacheDir = $args[$i + 1]  # 覆盖缓存目录。
                $i++  # 跳过值。
            }
        }
        '-venv-dir' {  # 解析 -venv-dir 参数。
            if ($i + 1 -lt $args.Length) {  # 校验值是否存在。
                $VenvDir = $args[$i + 1]  # 覆盖虚拟环境目录。
                $i++  # 跳过值。
            }
        }
        '-backend' {  # 解析 -backend 参数。
            if ($i + 1 -lt $args.Length) {  # 校验值是否存在。
                $ModelBackend = $args[$i + 1]  # 记录模型后端。
                $i++  # 跳过值。
            }
        }
        '-model' {  # 解析 -model 参数。
            if ($i + 1 -lt $args.Length) {  # 校验值是否存在。
                $ModelName = $args[$i + 1]  # 记录模型规格。
                $i++  # 跳过值。
            }
        }
        '-models-dir' {  # 解析 -models-dir 参数。
            if ($i + 1 -lt $args.Length) {  # 校验值是否存在。
                $ModelsDir = $args[$i + 1]  # 记录模型目录。
                $i++  # 跳过值。
            }
        }
        '-extra-index-url' {  # 解析 -extra-index-url 参数。
            if ($i + 1 -lt $args.Length) {  # 校验值是否存在。
                $ExtraIndexUrl = $args[$i + 1]  # 记录额外索引地址。
                $i++  # 跳过值。
            }
        }
        '-help' {  # 当用户请求帮助时。
            Show-Help  # 调用帮助函数。
            exit 0  # 输出帮助后退出。
        }
        default {  # 捕获未识别的参数。
            Write-Host "[WARN] 未识别的参数: $current"  # 输出警告。
        }
    }
}  # 完成参数解析。
Write-Host '---- 参数解析结果 ----'  # 打印标题。
Write-Host "check-only          : $CheckOnly"  # 展示 check-only 配置。
Write-Host ("python              : {0}" -f (if ($PythonPath) { $PythonPath } else { '<自动检测>' }))  # 展示 Python 路径或占位符。
Write-Host "use-system-ffmpeg   : $UseSystemFfmpeg"  # 展示 ffmpeg 策略。
Write-Host "cache-dir           : $CacheDir"  # 展示缓存目录。
Write-Host "venv-dir            : $VenvDir"  # 展示虚拟环境目录。
Write-Host "backend             : $ModelBackend"  # 展示模型后端。
Write-Host "model               : $ModelName"  # 展示模型规格。
Write-Host "models-dir          : $ModelsDir"  # 展示模型目录。
Write-Host ("extra-index-url     : {0}" -f (if ($ExtraIndexUrl) { $ExtraIndexUrl } else { '<未指定>' }))  # 展示额外索引。
Write-Host "仓库根目录          : $RepoRoot"  # 展示仓库根目录。
Write-Host ''  # 输出空行便于阅读。
function Resolve-Python {  # 定义函数用于确定 Python 解释器路径。
    if ($PythonPath) {  # 若用户已指定路径。
        return $PythonPath  # 直接返回该路径。
    }
    $candidates = @('python', 'python3')  # 按顺序尝试的命令列表。
    foreach ($name in $candidates) {  # 遍历候选名称。
        $command = Get-Command $name -ErrorAction SilentlyContinue  # 检查命令是否存在。
        if ($command) {  # 若找到可执行文件。
            return $command.Source  # 返回可执行路径。
        }
    }
    return ''  # 若未找到则返回空字符串。
}  # 结束解释器解析函数。
function Print-SystemInfo {  # 定义函数打印平台信息。
    Write-Host '---- 系统信息 ----'  # 打印标题。
    Write-Host ("操作系统         : {0}" -f [System.Runtime.InteropServices.RuntimeInformation]::OSDescription)  # 输出操作系统描述。
    Write-Host ("处理器架构       : {0}" -f [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture)  # 输出处理器架构。
    try {  # 尝试执行 python --version。
        $pyVersion = & python --version 2>$null  # 调用系统 python。
        if ($pyVersion) {  # 若命令返回结果。
            Write-Host "python --version  : $pyVersion"  # 打印版本。
        } else {
            Write-Host '[INFO] 未能获取系统 python 版本。'  # 提示缺失。
        }
    } catch {
        Write-Host '[INFO] python 命令不可用。'  # 捕获异常时提示。
    }
    try {  # 尝试执行 pip --version。
        $pipVersion = & pip --version 2>$null  # 调用系统 pip。
        if ($pipVersion) {  # 若命令返回结果。
            Write-Host "pip --version     : $pipVersion"  # 打印版本。
        } else {
            Write-Host '[INFO] 未能获取系统 pip 版本。'  # 提示缺失。
        }
    } catch {
        Write-Host '[INFO] pip 命令不可用。'  # 捕获异常时提示。
    }
    Write-Host ''  # 输出空行分隔。
}  # 结束系统信息函数。
function Ensure-Directory {  # 定义函数确保目录存在。
    param([string]$Path)  # 声明目录路径参数。
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {  # 判断目录是否存在。
        New-Item -ItemType Directory -Path $Path | Out-Null  # 若不存在则创建目录。
    }
}  # 结束目录创建函数。
function Run-Verify {  # 定义函数执行 verify_env.py 脚本。
    param([string]$PythonExecutable)  # 声明 Python 路径参数。
    & $PythonExecutable (Join-Path $ScriptDir 'verify_env.py') `  # 调用验证脚本并传参。
        --backend $ModelBackend `  # 传入后端参数。
        --model $ModelName `  # 传入模型规格。
        --models-dir $ModelsDir `  # 传入模型目录。
        --cache-dir $CacheDir  # 传入缓存目录。
}  # 结束体检函数。
function Invoke-Pip {  # 定义函数封装 python -m pip 调用。
    param(  # 声明参数块。
        [string]$PythonExecutable,  # Python 解释器路径。
        [string[]]$Arguments  # 传递给 pip 的参数列表。
    )
    & $PythonExecutable '-m' 'pip' @Arguments  # 使用 python -m pip 执行命令。
}  # 结束 pip 封装函数。
function Install-PythonRequirements {  # 定义函数安装项目依赖。
    param([string]$PythonExecutable)  # 传入虚拟环境中的 Python 路径。
    $upgradeArgs = @('install', '--upgrade', 'pip')  # 构造升级 pip 的参数。
    if ($ExtraIndexUrl) {  # 若用户指定额外索引。
        $upgradeArgs += @('--extra-index-url', $ExtraIndexUrl)  # 将索引附加到命令中。
    }
    Invoke-Pip -PythonExecutable $PythonExecutable -Arguments $upgradeArgs  # 执行 pip 升级。
    $installArgs = @('install', '-r', $RequirementsFile)  # 构造安装 requirements 的参数。
    if ($ExtraIndexUrl) {  # 若指定额外索引。
        $installArgs += @('--extra-index-url', $ExtraIndexUrl)  # 将索引附加到命令中。
    }
    Invoke-Pip -PythonExecutable $PythonExecutable -Arguments $installArgs  # 安装项目依赖。
}  # 结束依赖安装函数。
function Install-TorchCpu {  # 定义函数尝试安装 CPU 版 torch。
    param([string]$PythonExecutable)  # 传入虚拟环境中的 Python 路径。
    $torchArgs = @('install', 'torch', '--index-url', 'https://download.pytorch.org/whl/cpu')  # 构造安装 torch 的参数。
    if ($ExtraIndexUrl) {  # 若指定额外索引。
        $torchArgs += @('--extra-index-url', $ExtraIndexUrl)  # 追加索引参数。
    }
    try {  # 捕获可能的安装异常。
        Invoke-Pip -PythonExecutable $PythonExecutable -Arguments $torchArgs  # 尝试安装 torch。
        Write-Host '[INFO] torch CPU 版安装成功。'  # 输出成功提示。
    } catch {
        Write-Host '[WARN] torch 安装失败，将继续剩余流程。'  # 输出警告。
        Write-Host '[HINT] 请参考 README Round 5 章节手动安装匹配平台的 torch 轮子。'  # 提示用户后续操作。
    }
}  # 结束 torch 安装函数。
function Append-PathOnce {  # 定义函数将目录临时加入 PATH。
    param([string]$Directory)  # 声明目录参数。
    if (-not [string]::IsNullOrWhiteSpace($Directory)) {  # 确保目录字符串有效。
        $currentPaths = $env:PATH.Split([System.IO.Path]::PathSeparator)  # 拆分现有 PATH。
        if (-not ($currentPaths -contains $Directory)) {  # 若 PATH 中尚未包含该目录。
            $env:PATH = "$Directory$([System.IO.Path]::PathSeparator)$($env:PATH)"  # 将目录追加到 PATH 前端。
        }
    }
}  # 结束 PATH 更新函数。
function Get-PlatformTag {  # 定义函数识别平台标签。
    if ($IsWindows) { return 'windows' }  # Windows 平台直接返回 windows。
    if ($IsMacOS) { return 'macos' }  # macOS 平台返回 macos。
    if ($IsLinux) { return 'linux' }  # Linux 平台返回 linux。
    return 'unknown'  # 其他情况返回 unknown。
}  # 结束平台识别函数。
function Fetch-File {  # 定义函数下载文件。
    param(  # 声明参数块。
        [string]$Url,  # 文件 URL。
        [string]$Destination  # 保存路径。
    )
    if (Get-Command curl -ErrorAction SilentlyContinue) {  # 优先使用 curl。
        & curl -L --fail --show-error --output $Destination $Url  # 使用 curl 下载。
    } elseif (Get-Command wget -ErrorAction SilentlyContinue) {  # 无 curl 时退化到 wget。
        & wget -O $Destination $Url  # 使用 wget 下载。
    } else {  # 两者都不可用。
        throw "缺少 curl 或 wget，无法下载 $Url"  # 抛出异常提示用户。
    }
    if (-not (Test-Path -LiteralPath $Destination -PathType Leaf) -or (Get-Item $Destination).Length -eq 0) {  # 校验文件是否有效。
        throw "下载的文件为空或不存在：$Url"  # 抛出异常提示失败。
    }
}  # 结束下载函数。
function Expand-TarArchive {  # 定义函数解压 tar.xz 包。
    param(  # 声明参数块。
        [string]$ArchivePath,  # 压缩文件路径。
        [string]$Destination  # 解压目录。
    )
    if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {  # 若目标目录不存在。
        New-Item -ItemType Directory -Path $Destination | Out-Null  # 创建目录。
    }
    & tar -xf $ArchivePath -C $Destination  # 调用 tar 解压。
}  # 结束 tar 解压函数。
function Expand-ZipArchive {  # 定义函数解压 zip 包。
    param([string]$ArchivePath, [string]$Destination)  # 声明参数。
    if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {  # 若目标目录不存在。
        New-Item -ItemType Directory -Path $Destination | Out-Null  # 创建目录。
    }
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $Destination -Force  # 调用内置 Expand-Archive 解压 zip。
}  # 结束 zip 解压函数。
function Expand-7zArchive {  # 定义函数解压 7z 包。
    param([string]$ArchivePath, [string]$Destination)  # 声明参数。
    if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {  # 若目标目录不存在。
        New-Item -ItemType Directory -Path $Destination | Out-Null  # 创建目录。
    }
    $sevenZip = Get-Command 7z -ErrorAction SilentlyContinue  # 尝试查找 7z 命令。
    if (-not $sevenZip) {  # 若未找到 7z。
        throw '未检测到 7z，请通过 choco/winget 安装 7zip 后重试，或手动解压。'  # 抛出异常提示用户。
    }
    & $sevenZip.Path 'x' '-y' "-o$Destination" $ArchivePath  # 调用 7z 解压到目标目录。
}  # 结束 7z 解压函数。
function Download-Ffmpeg {  # 定义函数根据平台下载 ffmpeg 静态构建。
    param([string]$Platform, [string]$CacheRoot)  # 声明参数。
    Ensure-Directory -Path $CacheRoot  # 确保缓存目录存在。
    switch ($Platform) {  # 根据平台选择资源。
        'linux' {
            $archiveUrl = 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'  # Linux 静态构建链接。
            $archiveName = 'ffmpeg-release-amd64-static.tar.xz'  # 下载文件名。
            $targetDir = Join-Path $CacheRoot 'ffmpeg-linux'  # 解压目录。
            Ensure-Directory -Path $targetDir  # 确保目录存在。
            $archivePath = Join-Path $targetDir $archiveName  # 构造文件路径。
            if (-not (Test-Path -LiteralPath $archivePath)) {  # 若文件不存在。
                Write-Host "[INFO] 正在下载 ffmpeg 静态包：$archiveUrl"  # 打印下载提示。
                Fetch-File -Url $archiveUrl -Destination $archivePath  # 下载文件。
            } else {
                Write-Host '[INFO] 检测到已下载的 ffmpeg 包，跳过重新下载。'  # 提示已存在。
            }
            $extractDir = Join-Path $targetDir 'extracted'  # 定义解压目录。
            if (-not (Test-Path -LiteralPath $extractDir -PathType Container)) {  # 若尚未解压。
                Write-Host '[INFO] 正在解压 ffmpeg 包。'  # 打印提示。
                Expand-TarArchive -ArchivePath $archivePath -Destination $extractDir  # 解压文件。
            } else {
                Write-Host '[INFO] 已存在解压目录，保持幂等。'  # 提示重复执行。
            }
            return (Join-Path $extractDir 'ffmpeg-*')  # 返回目录通配符。
        }
        'macos' {
            $archiveUrl = 'https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-macos64-static.zip'  # macOS 静态构建链接。
            $archiveName = 'ffmpeg-macos.zip'  # 下载文件名。
            $targetDir = Join-Path $CacheRoot 'ffmpeg-macos'  # 解压目录。
            Ensure-Directory -Path $targetDir  # 确保目录存在。
            $archivePath = Join-Path $targetDir $archiveName  # 构造文件路径。
            if (-not (Test-Path -LiteralPath $archivePath)) {
                Write-Host "[INFO] 正在下载 ffmpeg 静态包：$archiveUrl"  # 打印下载提示。
                Fetch-File -Url $archiveUrl -Destination $archivePath  # 下载文件。
            } else {
                Write-Host '[INFO] 检测到已下载的 ffmpeg 包，跳过重新下载。'  # 提示已存在。
            }
            $extractDir = Join-Path $targetDir 'extracted'  # 定义解压目录。
            if (-not (Test-Path -LiteralPath $extractDir -PathType Container)) {  # 若尚未解压。
                Write-Host '[INFO] 正在解压 ffmpeg 包。'  # 打印提示。
                Expand-ZipArchive -ArchivePath $archivePath -Destination $extractDir  # 解压 zip 文件。
            } else {
                Write-Host '[INFO] 已存在解压目录，保持幂等。'  # 提示重复执行。
            }
            return (Join-Path $extractDir 'ffmpeg-master-latest-macos64-static/bin')  # 返回 bin 目录。
        }
        'windows' {
            $archiveUrl = 'https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-git-essentials.7z'  # Windows 静态构建链接。
            $archiveName = 'ffmpeg-windows.7z'  # 下载文件名。
            $targetDir = Join-Path $CacheRoot 'ffmpeg-windows'  # 解压目录。
            Ensure-Directory -Path $targetDir  # 确保目录存在。
            $archivePath = Join-Path $targetDir $archiveName  # 构造文件路径。
            if (-not (Test-Path -LiteralPath $archivePath)) {
                Write-Host "[INFO] 正在下载 ffmpeg 静态包：$archiveUrl"  # 打印下载提示。
                Fetch-File -Url $archiveUrl -Destination $archivePath  # 下载文件。
            } else {
                Write-Host '[INFO] 检测到已下载的 ffmpeg 包，跳过重新下载。'  # 提示已存在。
            }
            $extractDir = Join-Path $targetDir 'extracted'  # 定义解压目录。
            if (-not (Test-Path -LiteralPath $extractDir -PathType Container)) {
                Write-Host '[INFO] 正在解压 ffmpeg 包。'  # 打印提示。
                Expand-7zArchive -ArchivePath $archivePath -Destination $extractDir  # 解压 7z 文件。
            } else {
                Write-Host '[INFO] 已存在解压目录，保持幂等。'  # 提示重复执行。
            }
            return (Join-Path $extractDir 'ffmpeg-*/bin')  # 返回 bin 目录。
        }
        default {
            return ''  # 未识别平台时返回空字符串。
        }
    }
}  # 结束下载函数。
function Resolve-FfmpegDirectory {  # 定义函数从通配符中定位具体目录。
    param([string]$Pattern)  # 声明通配符参数。
    $matches = Get-ChildItem -Path $Pattern -Directory -ErrorAction SilentlyContinue  # 查找匹配目录。
    if ($matches -and $matches.Count -gt 0) {  # 若找到至少一个目录。
        return $matches[0].FullName  # 返回第一个匹配项。
    }
    return ''  # 否则返回空字符串。
}  # 结束目录解析函数。
function Prepare-Ffmpeg {  # 定义函数处理 ffmpeg 准备逻辑。
    param([string]$Platform, [string]$CacheRoot)  # 声明参数。
    if ($UseSystemFfmpeg -eq 'true') {  # 当用户希望优先使用系统 ffmpeg。
        $ffmpegPath = Get-Command ffmpeg -ErrorAction SilentlyContinue  # 查找 ffmpeg。
        $ffprobePath = Get-Command ffprobe -ErrorAction SilentlyContinue  # 查找 ffprobe。
        if ($ffmpegPath -and $ffprobePath) {  # 若两个命令均存在。
            Write-Host "[INFO] 已检测到系统 ffmpeg/ffprobe：$($ffmpegPath.Path)"  # 输出确认。
            return
        }
        Write-Host '[WARN] 系统中未找到 ffmpeg/ffprobe，准备下载静态构建。'  # 提示即将下载。
    } else {
        Write-Host '[INFO] 用户设置 use-system-ffmpeg=false，将下载静态构建。'  # 输出说明。
    }
    $pattern = Download-Ffmpeg -Platform $Platform -CacheRoot $CacheRoot  # 下载并获取目录通配符。
    if (-not $pattern) {  # 若函数返回空字符串。
        Write-Host '[ERROR] 未能提供适配当前平台的 ffmpeg 包，请参考 README 手动安装。'  # 输出错误。
        return
    }
    $directory = Resolve-FfmpegDirectory -Pattern $pattern  # 从通配符定位具体目录。
    if (-not $directory) {  # 若未找到有效目录。
        Write-Host '[ERROR] 未能定位解压后的 ffmpeg 目录，请检查下载与解压步骤。'  # 输出错误。
        return
    }
    Append-PathOnce -Directory $directory  # 将目录加入当前会话的 PATH。
    Write-Host "[INFO] 已将 $directory 加入 PATH（仅当前会话有效）。"  # 提示用户 PATH 已更新。
}  # 结束 ffmpeg 准备函数。
function Ensure-Venv {  # 定义函数创建虚拟环境。
    param([string]$PythonExecutable, [string]$VenvPath)  # 声明参数。
    if (-not (Test-Path -LiteralPath (Join-Path $VenvPath 'pyvenv.cfg'))) {  # 若虚拟环境尚未创建。
        Write-Host "[INFO] 正在创建虚拟环境：$VenvPath"  # 输出提示。
        & $PythonExecutable '-m' 'venv' $VenvPath  # 创建虚拟环境。
    } else {
        Write-Host '[INFO] 检测到已存在的虚拟环境，跳过创建步骤。'  # 输出提示。
    }
}  # 结束虚拟环境函数。
function Activate-Venv {  # 定义函数激活虚拟环境。
    param([string]$VenvPath)  # 声明参数。
    $activateScript = Join-Path $VenvPath 'Scripts\Activate.ps1'  # Windows 激活脚本路径。
    if (-not (Test-Path -LiteralPath $activateScript)) {  # 若不存在 Windows 激活脚本。
        $activateScript = Join-Path $VenvPath 'bin/activate.ps1'  # 尝试定位 PowerShell Core 在类 Unix 下的激活脚本。
    }
    if (-not (Test-Path -LiteralPath $activateScript)) {  # 若仍未找到。
        throw "未找到虚拟环境激活脚本：$activateScript"  # 抛出异常提示。
    }
    . $activateScript  # 点调用激活脚本以更新当前会话。
}  # 结束激活函数。
function Get-VenvPython {  # 定义函数返回虚拟环境中的 Python 路径。
    param([string]$VenvPath)  # 声明参数。
    $windowsPython = Join-Path $VenvPath 'Scripts\python.exe'  # Windows 路径。
    if (Test-Path -LiteralPath $windowsPython) {  # 若存在 python.exe。
        return $windowsPython  # 返回 Windows Python。
    }
    $unixPython = Join-Path $VenvPath 'bin/python'  # 类 Unix 路径。
    return $unixPython  # 返回默认路径（假定存在）。
}  # 结束获取 Python 函数。
function Main {  # 定义主函数组织整体流程。
    Print-SystemInfo  # 输出系统信息。
    $pythonExecutable = Resolve-Python  # 确定 Python 解释器路径。
    if (-not $pythonExecutable) {  # 若未找到解释器。
        Write-Host '[ERROR] 未找到可用的 Python 解释器，请使用 -python 指定。'  # 输出错误。
        exit 1  # 以非零状态退出。
    }
    Write-Host "[INFO] 将使用 Python 解释器：$pythonExecutable"  # 输出即将使用的解释器。
    if ($CheckOnly -eq 'true') {  # 当用户选择仅检查。
        Write-Host '[INFO] 处于 check-only 模式，仅执行 verify_env.py。'  # 输出模式说明。
        Run-Verify -PythonExecutable $pythonExecutable  # 执行体检脚本。
        return
    }
    Ensure-Directory -Path $CacheDir  # 创建缓存目录。
    Ensure-Directory -Path $VenvDir  # 创建虚拟环境目录。
    Ensure-Venv -PythonExecutable $pythonExecutable -VenvPath $VenvDir  # 创建虚拟环境。
    Activate-Venv -VenvPath $VenvDir  # 激活虚拟环境。
    $venvPython = Get-VenvPython -VenvPath $VenvDir  # 获取虚拟环境 Python 路径。
    Install-PythonRequirements -PythonExecutable $venvPython  # 安装基础依赖。
    Install-TorchCpu -PythonExecutable $venvPython  # 尝试安装 torch。
    $platform = Get-PlatformTag  # 检测当前平台。
    $ffmpegCache = Join-Path $CacheDir 'ffmpeg'  # 构造 ffmpeg 缓存目录。
    Ensure-Directory -Path $ffmpegCache  # 确保 ffmpeg 缓存目录存在。
    try {  # 捕获 ffmpeg 准备过程中可能的异常。
        Prepare-Ffmpeg -Platform $platform -CacheRoot $ffmpegCache  # 处理 ffmpeg 准备逻辑。
    } catch {
        Write-Host "[WARN] 自动准备 ffmpeg 失败：$($_.Exception.Message)"  # 输出警告。
        Write-Host '[HINT] 请参考 README Round 5 章节手动安装 ffmpeg/ffprobe。'  # 提供建议。
    }
    Write-Host '[INFO] 准备执行模型下载流程。'  # 提示即将调用模型下载脚本。
    $downloadScript = Join-Path $ScriptDir 'download_model.py'  # 计算模型下载脚本路径。
    $downloadArgs = @('--backend', $ModelBackend, '--model', $ModelName, '--cache-dir', $CacheDir)  # 构建基础参数数组。
    if ($ModelsDir) {  # 若模型目录参数非空。
        $downloadArgs += @('--models-dir', $ModelsDir)  # 将模型目录追加到参数中。
    }
    $displayArgs = $downloadArgs -join ' '  # 组装用于展示的参数字符串。
    Write-Host "[INFO] 调用模型下载器：$venvPython $downloadScript $displayArgs"  # 打印即将执行的命令。
    $downloadOutput = & $venvPython $downloadScript @downloadArgs 2>&1  # 执行模型下载脚本并捕获输出。
    $downloadExit = $LASTEXITCODE  # 记录退出码。
    if ($downloadOutput) {  # 若脚本产生输出。
        ($downloadOutput -split "`n") | ForEach-Object { Write-Host $_ }  # 逐行回显日志。
    }
    if ($downloadExit -eq 0 -and $downloadOutput) {  # 成功且有输出时。
        $downloadLines = $downloadOutput -split "`n"  # 将输出拆分成数组。
        $downloadJsonCandidates = $downloadLines | Where-Object { $_.Trim().Length -gt 0 }  # 过滤出非空行。
        if ($downloadJsonCandidates.Count -gt 0) {  # 若存在非空行。
            $downloadJson = $downloadJsonCandidates[$downloadJsonCandidates.Count - 1]  # 获取最后一个非空行作为 JSON。
            Write-Host "[INFO] 模型下载结果 JSON：$downloadJson"  # 打印 JSON 结果。
        }
    } elseif ($downloadExit -ne 0) {  # 当退出码非零时。
        Write-Host "[WARN] 模型下载脚本退出码为 $downloadExit，请稍后重试或参考 README 手动准备模型。"  # 提示后续步骤。
    }
    Write-Host '[INFO] 开始运行 verify_env.py 进行最终体检。'  # 提示接下来执行体检。
    Run-Verify -PythonExecutable $venvPython  # 使用虚拟环境 Python 执行体检。
    Write-Host ''  # 输出空行提升可读性。
    Write-Host '[INFO] 安装流程完成。'  # 输出完成提示。
    Write-Host "[NEXT] 运行以下命令继续体验："  # 提供下一步建议。
    Write-Host "       . $((Join-Path $VenvDir 'Scripts\Activate.ps1'))"  # 指导激活虚拟环境（Windows）。
    Write-Host "       source $VenvDir/bin/activate"  # 提供类 Unix 激活命令以兼容多平台。
    Write-Host '       python -m src.cli.main --help'  # 提示示例命令。
}  # 结束主函数。
Main  # 调用主函数启动脚本。
