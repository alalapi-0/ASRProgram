#!/usr/bin/env pwsh
# 上述 shebang 便于在安装了 PowerShell Core 的系统上直接执行脚本。
$ErrorActionPreference = 'Stop'  # 配置遇到错误时立即抛出异常。
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'  # 确保输出文件（若有）使用 UTF-8 编码。
$ScriptDir = Split-Path -LiteralPath $MyInvocation.MyCommand.Path -Parent  # 解析脚本所在目录。
$RepoRoot = Resolve-Path (Join-Path $ScriptDir '..')  # 推断仓库根目录位置。
$CheckOnly = 'true'  # 默认仅演练，不执行真实安装。
$Backend = 'faster-whisper'  # 默认后端为 faster-whisper。
$Model = 'medium'  # 默认模型规格为 medium。
$UseSystemFfmpeg = 'true'  # 默认复用系统 ffmpeg。
$PythonPath = ''  # 默认不指定自定义 Python，可使用系统路径。
$CacheDir = '.cache/'  # 默认缓存目录，保持相对路径形式。
function Show-Help {  # 定义帮助函数输出脚本文档。
    Write-Host 'ASRProgram Round 2 安装演练脚本 (PowerShell 版)'  # 打印标题。
    Write-Host '参数列表：'  # 简要介绍参数。
    Write-Host '  -check-only [true|false]       是否仅演练步骤，默认 true。'  # 说明 check-only。
    Write-Host '  -backend [faster-whisper|whisper.cpp]  规划使用的后端，默认 faster-whisper。'  # 说明 backend。
    Write-Host '  -model [tiny|base|small|medium|large-v3]  规划下载的模型规格，默认 medium。'  # 说明 model。
    Write-Host '  -use-system-ffmpeg [true|false]  是否尝试复用系统 ffmpeg，默认 true。'  # 说明 ffmpeg。
    Write-Host '  -python <path>                 指定未来将用于创建虚拟环境的解释器。'  # 说明 python 参数。
    Write-Host '  -cache-dir <path>              指定缓存目录，默认 .cache/。'  # 说明缓存目录。
    Write-Host '  -help                          查看此帮助信息。'  # 说明帮助参数。
}  # 结束帮助函数定义。
for ($i = 0; $i -lt $args.Length; $i++) {  # 使用循环解析传入的脚本参数。
    $current = $args[$i]  # 读取当前参数。
    switch ($current) {  # 根据参数名称分支处理。
        '-check-only' {  # 处理 -check-only 选项。
            if ($i + 1 -lt $args.Length) {  # 确保存在对应的值。
                $CheckOnly = $args[$i + 1]  # 记录用户提供的取值。
                $i++  # 跳过值以继续解析。
            }
        }
        '-backend' {  # 处理 -backend 选项。
            if ($i + 1 -lt $args.Length) {  # 确保存在对应的值。
                $Backend = $args[$i + 1]  # 更新后端选择。
                $i++  # 跳过值。
            }
        }
        '-model' {  # 处理 -model 选项。
            if ($i + 1 -lt $args.Length) {  # 确保存在对应的值。
                $Model = $args[$i + 1]  # 更新模型规格。
                $i++  # 跳过值。
            }
        }
        '-use-system-ffmpeg' {  # 处理 -use-system-ffmpeg 选项。
            if ($i + 1 -lt $args.Length) {  # 确保存在对应的值。
                $UseSystemFfmpeg = $args[$i + 1]  # 记录用户选择。
                $i++  # 跳过值。
            }
        }
        '-python' {  # 处理 -python 选项。
            if ($i + 1 -lt $args.Length) {  # 确保存在对应的值。
                $PythonPath = $args[$i + 1]  # 记录用户指定的解释器路径。
                $i++  # 跳过值。
            }
        }
        '-cache-dir' {  # 处理 -cache-dir 选项。
            if ($i + 1 -lt $args.Length) {  # 确保存在对应的值。
                $CacheDir = $args[$i + 1]  # 记录缓存目录。
                $i++  # 跳过值。
            }
        }
        '-help' {  # 处理 -help 选项。
            Show-Help  # 调用帮助函数。
            exit 0  # 输出帮助后退出脚本。
        }
        default {  # 捕获所有未识别的参数。
            Write-Host "[WARN] 未识别的参数: $current"  # 提示用户输入无法识别。
        }
    }
}  # 完成参数解析。
Write-Host '---- 参数解析结果 ----'  # 打印标题。
Write-Host "check-only          : $CheckOnly"  # 展示 check-only 值。
Write-Host "backend             : $Backend"  # 展示后端选择。
Write-Host "model               : $Model"  # 展示模型规格。
Write-Host "use-system-ffmpeg   : $UseSystemFfmpeg"  # 展示 ffmpeg 使用策略。
Write-Host ("python              : {0}" -f (if ($PythonPath) { $PythonPath } else { '<系统默认>' }))  # 展示 Python 路径或占位符。
Write-Host "cache-dir           : $CacheDir"  # 展示缓存目录。
Write-Host "仓库根目录          : $RepoRoot"  # 提醒用户路径基准。
Write-Host ''  # 输出空行用于分隔。
if ($CheckOnly -notin @('true', 'false')) {  # 检查 check-only 值是否合法。
    Write-Host "[WARN] -check-only 建议使用 true 或 false，当前值: $CheckOnly"  # 输出提醒。
}
if ($Backend -notin @('faster-whisper', 'whisper.cpp')) {  # 检查 backend 是否在允许列表。
    Write-Host "[WARN] -backend 仅支持 faster-whisper 或 whisper.cpp，当前值: $Backend"  # 输出警告。
}
if ($Model -notin @('tiny', 'base', 'small', 'medium', 'large-v3')) {  # 检查模型规格。
    Write-Host "[WARN] -model 建议取值 tiny|base|small|medium|large-v3，当前值: $Model"  # 输出提醒。
}
if ($UseSystemFfmpeg -notin @('true', 'false')) {  # 检查 use-system-ffmpeg。
    Write-Host "[WARN] -use-system-ffmpeg 建议使用 true 或 false，当前值: $UseSystemFfmpeg"  # 输出警告。
}
if ($PythonPath) {  # 判断是否指定了 Python 路径。
    if (Test-Path -LiteralPath $PythonPath) {  # 检查路径是否存在。
        $pythonCommand = Get-Command -ErrorAction SilentlyContinue -LiteralPath $PythonPath  # 尝试解析命令信息。
        if ($pythonCommand) {  # 若解析成功。
            Write-Host "[INFO] 指定的 Python 可执行：$($pythonCommand.Path)"  # 输出确认信息。
        } else {  # 解析失败说明不可执行。
            Write-Host "[WARN] 指定的 Python 路径存在但不可执行：$PythonPath"  # 输出提醒。
        }
    } else {  # 路径不存在。
        Write-Host "[WARN] 指定的 Python 路径不存在：$PythonPath"  # 输出提醒。
    }
} else {  # 未指定 python 的情况。
    Write-Host '[INFO] 未指定 -python，后续将使用系统默认 python。'  # 提示将使用默认解释器。
}
Write-Host ''  # 输出空行便于阅读。
Write-Host '---- 系统信息检测 ----'  # 打印系统信息标题。
Write-Host ("操作系统         : {0}" -f [System.Runtime.InteropServices.RuntimeInformation]::OSDescription)  # 输出操作系统描述。
Write-Host ("处理器架构       : {0}" -f [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture)  # 输出处理器架构。
try {  # 捕获调用 python 时可能的异常。
    $pyVersion = & python --version 2>$null  # 调用系统 python 并捕获版本信息。
    if ($pyVersion) {  # 如果获取成功。
        Write-Host "python --version  : $pyVersion"  # 打印版本。
    } else {  # 如果命令返回空值。
        Write-Host '[INFO] python 命令不可用或无输出。'  # 提供提示。
    }
} catch {  # 捕获异常。
    Write-Host '[INFO] python 命令不可用。'  # 输出提示。
}
try {  # 捕获 pip 命令可能的异常。
    $pipVersion = & pip --version 2>$null  # 调用 pip 命令。
    if ($pipVersion) {  # 判断是否获取到版本号。
        Write-Host "pip --version     : $pipVersion"  # 打印版本信息。
    } else {  # 没有获取到信息。
        Write-Host '[INFO] pip 命令不可用或无输出。'  # 提供提示。
    }
} catch {  # 捕获异常。
    Write-Host '[INFO] pip 命令不可用。'  # 输出提示。
}
Write-Host ''  # 输出空行便于阅读。
Write-Host '---- ffmpeg / ffprobe 探测 ----'  # 打印多媒体工具检测标题。
$ffmpegPath = Get-Command ffmpeg -ErrorAction SilentlyContinue  # 查找 ffmpeg 可执行。
if ($ffmpegPath) {  # 判断是否找到 ffmpeg。
    Write-Host "ffmpeg 已在 PATH 中：$($ffmpegPath.Path)"  # 输出路径。
} else {  # 未找到时。
    Write-Host '未在 PATH 中找到 ffmpeg。'  # 提供提示。
}
$ffprobePath = Get-Command ffprobe -ErrorAction SilentlyContinue  # 查找 ffprobe 可执行。
if ($ffprobePath) {  # 判断是否找到 ffprobe。
    Write-Host "ffprobe 已在 PATH 中：$($ffprobePath.Path)"  # 输出路径。
} else {  # 未找到时。
    Write-Host '未在 PATH 中找到 ffprobe。'  # 提供提示。
}
Write-Host ''  # 输出空行便于阅读。
Write-Host '---- 目录预检 ----'  # 打印目录检查标题。
$directories = @('.cache', 'out')  # 列出需要关注的目录。
foreach ($dir in $directories) {  # 遍历每个目录。
    $target = Join-Path $RepoRoot $dir  # 组合绝对路径。
    if (Test-Path -LiteralPath $target -PathType Container) {  # 判断目录是否存在。
        if (Test-DirectoryWritable -Path $target) {  # 调用自定义函数检查可写性。
            Write-Host "$dir 已存在且可写。"  # 输出正常状态。
        } else {  # 当目录不可写或无法确定。
            Write-Host "$dir 已存在但可能不可写，后续安装需确认权限。"  # 输出提醒。
        }
    } else {  # 目录不存在。
        Write-Host "$dir 尚未创建，将在未来的真实安装步骤中自动创建。"  # 说明不会立即创建。
    }
}
Write-Host ''  # 输出空行便于阅读。
Write-Host '---- 计划步骤（仅打印，不执行） ----'  # 标记演练模式。
if ($CheckOnly -eq 'true') {  # 判断是否处于演练模式。
    Write-Host '当前为 check-only 演练模式，不会执行任何写操作。'  # 强调演练。
} else {  # 当用户设为 false 时。
    Write-Host '当前为计划演练模式：即便 check-only=false，本轮仍仅打印计划。'  # 再次强调不执行。
}
Write-Host '1. 创建虚拟环境：python -m venv .venv'  # 描述未来将执行的命令。
Write-Host '2. 激活虚拟环境：在 PowerShell 中运行 .\.venv\Scripts\Activate.ps1（或对应平台命令）'  # 说明激活方式。
Write-Host '3. 安装依赖：pip install -r requirements.txt'  # 预告依赖安装。
Write-Host ("4. ffmpeg 策略：系统已有则跳过；无则按平台下载到 {0}ffmpeg/ 并加入 PATH（未来实现）。" -f $CacheDir)  # 解释多媒体策略。
Write-Host ("5. 下载模型：python scripts/download_model.py --backend {0} --model {1} --cache-dir {2}" -f $Backend, $Model, $CacheDir)  # 演示未来的模型下载命令。
if ($Backend -eq 'whisper.cpp') {  # 针对 whisper.cpp 后端补充说明。
    Write-Host '6. whisper.cpp 路线：未来将克隆仓库、执行 cmake/make 或下载预编译包，并在 config/default.yaml 中写入可执行路径。'  # 提醒额外步骤。
} else {  # 当用户选择 faster-whisper 时。
    Write-Host '6. whisper.cpp 路线：当前未选择，但仍会在未来文档中提供编译与配置说明。'  # 仍提示存在该路线。
}
Write-Host '所有上述步骤在 Round 2 中仅作为演练展示，真实安装计划将于后续轮次启用。'  # 提供时间表。
Write-Host ''  # 输出空行以分隔自检结果。
Write-Host '以下为真实探测结果：'  # 提示接下来是实际执行。
if ($PythonPath -and (Test-Path -LiteralPath $PythonPath)) {  # 若用户指定且路径存在。
    & $PythonPath (Join-Path $ScriptDir 'verify_env.py')  # 使用指定解释器运行体检。
} else {  # 未指定或路径不存在。
    & python (Join-Path $ScriptDir 'verify_env.py')  # 使用系统默认 python 执行。
}
exit 0  # 明确返回状态码 0。

function Test-DirectoryWritable {  # 定义函数用于评估目录可写性。
    param (  # 声明参数块。
        [Parameter(Mandatory = $true)]
        [string]$Path  # 需要检测的目录路径。
    )
    try {  # 尝试读取 ACL 信息以判断写权限。
        $directoryInfo = [System.IO.DirectoryInfo]::new($Path)  # 创建目录信息对象。
        $acl = $directoryInfo.GetAccessControl()  # 读取访问控制列表。
        $rules = $acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])  # 获取与用户和组相关的规则。
        $currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()  # 获取当前用户标识。
        $principal = [System.Security.Principal.WindowsPrincipal]::new($currentIdentity)  # 构建 WindowsPrincipal 以便判断角色。
        foreach ($rule in $rules) {  # 遍历所有规则。
            if ($principal.IsInRole($rule.IdentityReference)) {  # 判断规则是否适用于当前用户或其所在组。
                if (($rule.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Write) -and $rule.AccessControlType -eq 'Allow') {  # 检查是否授予写权限。
                    return $true  # 若满足则视为可写。
                }
            }
        }
        return $false  # 若未命中允许写入的规则，则视为不可写或无法确定。
    } catch {  # 捕获任何异常。
        return $false  # 在无法解析权限时返回 false。
    }
}
