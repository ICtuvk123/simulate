param(
    [Parameter(Mandatory = $true)]
    [string]$PythonPath,
    [switch]$SelfCheck,
    [string]$PreviewPath = ''
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$script:ProjectPath = Split-Path -Parent $PSScriptRoot
$script:BackendPath = Join-Path $PSScriptRoot 'test_helper.py'
$script:ResultsPath = Join-Path $script:ProjectPath 'user_tests'
$script:RunProcess = $null
$script:OutputTask = $null
$script:ErrorTask = $null
$script:StartedAt = $null
$script:RunLabel = ''
$script:LastExitCode = $null
$script:BusyControls = New-Object System.Collections.Generic.List[System.Windows.Forms.Control]

function New-Label([string]$Text, [int]$Left, [int]$Top, [int]$Width = 700) {
    $control = New-Object System.Windows.Forms.Label
    $control.Text = $Text
    $control.SetBounds($Left, $Top, $Width, 28)
    $control.AutoSize = $false
    return $control
}

function New-TextBox([string]$Text, [int]$Left, [int]$Top, [int]$Width) {
    $control = New-Object System.Windows.Forms.TextBox
    $control.Text = $Text
    $control.SetBounds($Left, $Top, $Width, 30)
    $script:BusyControls.Add($control)
    return $control
}

function New-Button([string]$Text, [int]$Left, [int]$Top, [int]$Width = 160) {
    $control = New-Object System.Windows.Forms.Button
    $control.Text = $Text
    $control.SetBounds($Left, $Top, $Width, 38)
    $control.UseVisualStyleBackColor = $true
    return $control
}

function Quote-ProcessArgument([string]$Value) {
    # Windows command-line quoting; no shell is involved in starting Python.
    $escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}

function Set-Busy([bool]$Busy) {
    foreach ($control in $script:BusyControls) {
        $control.Enabled = -not $Busy
    }
    $script:Progress.Style = if ($Busy) {
        [System.Windows.Forms.ProgressBarStyle]::Marquee
    } else {
        [System.Windows.Forms.ProgressBarStyle]::Blocks
    }
    $script:Progress.Value = 0
}

function Show-InputError([string]$Message) {
    [void][System.Windows.Forms.MessageBox]::Show(
        $script:Form, $Message, '请检查输入',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information)
}

function Start-Test([string]$Label, [string[]]$BackendArguments) {
    if ($null -ne $script:RunProcess) { return }
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        Show-InputError "没有找到 Python：$PythonPath`r`n请使用项目中的一键测试入口。"
        return
    }
    if (-not (Test-Path -LiteralPath $script:BackendPath -PathType Leaf)) {
        Show-InputError "没有找到测试程序：$script:BackendPath"
        return
    }
    $process = New-Object System.Diagnostics.Process
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $PythonPath
    $allArguments = @('-u', $script:BackendPath) + $BackendArguments
    $info.Arguments = (($allArguments | ForEach-Object { Quote-ProcessArgument $_ }) -join ' ')
    $info.WorkingDirectory = $script:ProjectPath
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $info.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $process.StartInfo = $info
    try {
        [void]$process.Start()
        $script:RunProcess = $process
        $script:OutputTask = $process.StandardOutput.ReadToEndAsync()
        $script:ErrorTask = $process.StandardError.ReadToEndAsync()
        $script:StartedAt = [DateTime]::Now
        $script:RunLabel = $Label
        $script:LastExitCode = $null
        Set-Busy $true
        $script:Output.Text = "$Label 正在运行。完成后会在这里显示结果。`r`n`r`n界面会持续更新运行时间，请保持官方模拟器开启。"
        $script:Status.Text = "$Label · 已运行 0 秒"
        $script:Timer.Start()
    } catch {
        if ($null -eq $script:RunProcess) { $process.Dispose() }
        $script:Output.Text = "无法启动测试：$($_.Exception.Message)"
        $script:Status.Text = '启动失败'
        Set-Busy $false
    }
}

$script:Form = New-Object System.Windows.Forms.Form
$script:Form.Text = '问题 3 · G+ 测试助手'
$script:Form.ClientSize = New-Object System.Drawing.Size(920, 710)
$script:Form.MinimumSize = New-Object System.Drawing.Size(920, 700)
$script:Form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$script:Form.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10)
$script:Form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Dpi
$script:Form.BackColor = [System.Drawing.Color]::FromArgb(246, 248, 251)

$heading = New-Label '问题 3 · G+ 测试助手' 22 17 600
$heading.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 17, [System.Drawing.FontStyle]::Bold)
$heading.Height = 38
$script:Form.Controls.Add($heading)
$subheading = New-Label '团队 202617201735  |  选择演练或本地测试，结果自动保存。' 24 62 840
$subheading.ForeColor = [System.Drawing.Color]::FromArgb(80, 91, 109)
$script:Form.Controls.Add($subheading)

$tabs = New-Object System.Windows.Forms.TabControl
$tabs.SetBounds(22, 103, 876, 295)
$tabs.Anchor = 'Top, Left, Right'
$tabs.Padding = New-Object System.Drawing.Point(20, 9)
$officialTab = New-Object System.Windows.Forms.TabPage
$officialTab.Text = '官方模拟演练'
$officialTab.BackColor = [System.Drawing.Color]::White
$localTab = New-Object System.Windows.Forms.TabPage
$localTab.Text = '本地模拟测试'
$localTab.BackColor = [System.Drawing.Color]::White
[void]$tabs.TabPages.Add($officialTab)
[void]$tabs.TabPages.Add($localTab)
$script:Form.Controls.Add($tabs)

$officialTab.Controls.Add((New-Label '1. 打开官方模拟器并登录，选择“问题3演练测试”。' 18 14 800))
$officialTab.Controls.Add((New-Label '2. 等待倒计时结束、接口开放，然后填写当前案例编号。' 18 43 800))
$officialTab.Controls.Add((New-Label '参赛队号' 18 89 95))
$teamBox = New-TextBox '202617201735' 119 85 220
$officialTab.Controls.Add($teamBox)
$officialTab.Controls.Add((New-Label '接口端口' 373 89 90))
$portBox = New-TextBox '2026' 470 85 110
$officialTab.Controls.Add($portBox)
$officialTab.Controls.Add((New-Label '当前案例编号' 18 132 110))
$caseBox = New-TextBox '' 135 128 445
$caseBox.CharacterCasing = [System.Windows.Forms.CharacterCasing]::Upper
$officialTab.Controls.Add($caseBox)
$hint = New-Label '格式：XXXX-XXXX-XXXX-XXXX' 591 132 250
$hint.ForeColor = [System.Drawing.Color]::DimGray
$officialTab.Controls.Add($hint)
$readyCheck = New-Object System.Windows.Forms.CheckBox
$readyCheck.Text = '我已核对当前页面为“问题3演练测试”，倒计时已结束，接口已开放。'
$readyCheck.SetBounds(20, 169, 800, 30)
$script:BusyControls.Add($readyCheck)
$officialTab.Controls.Add($readyCheck)
$officialButton = New-Button '开始 G+ 官方演练' 20 208 210
$script:BusyControls.Add($officialButton)
$officialTab.Controls.Add($officialButton)
$officialTab.Controls.Add((New-Label '本次只运行当前一场演练。' 248 215 570))

$localTab.Controls.Add((New-Label '在自建模拟器运行完整策略，可用同一种子比较 G+ 与旧 G。' 18 18 805))
$localTab.Controls.Add((New-Label '随机种子' 18 71 100))
$seedBox = New-TextBox '13001' 125 66 180
$localTab.Controls.Add($seedBox)
$baselineCheck = New-Object System.Windows.Forms.CheckBox
$baselineCheck.Text = '使用旧 G 基线进行对比（不勾选时运行 G+）'
$baselineCheck.SetBounds(20, 113, 790, 30)
$script:BusyControls.Add($baselineCheck)
$localTab.Controls.Add($baselineCheck)
$localTab.Controls.Add((New-Label '种子相同表示同一场景；更换种子可观察不同场景下的平均时间。' 18 158 805))
$localButton = New-Button '开始本地测试' 20 208 210
$script:BusyControls.Add($localButton)
$localTab.Controls.Add($localButton)

$checkButton = New-Button '检查运行环境' 22 414 155
$script:BusyControls.Add($checkButton)
$script:Form.Controls.Add($checkButton)
$resultsButton = New-Button '打开测试结果' 190 414 155
$script:Form.Controls.Add($resultsButton)
$script:Status = New-Label '就绪 · 官方演练默认使用冻结 G+ 策略' 363 423 530
$script:Status.Anchor = 'Top, Left, Right'
$script:Form.Controls.Add($script:Status)
$script:Progress = New-Object System.Windows.Forms.ProgressBar
$script:Progress.SetBounds(22, 464, 876, 6)
$script:Progress.Anchor = 'Top, Left, Right'
$script:Progress.MarqueeAnimationSpeed = 25
$script:Form.Controls.Add($script:Progress)
$script:Output = New-Object System.Windows.Forms.TextBox
$script:Output.SetBounds(22, 483, 876, 205)
$script:Output.Anchor = 'Top, Bottom, Left, Right'
$script:Output.Multiline = $true
$script:Output.ReadOnly = $true
$script:Output.ScrollBars = [System.Windows.Forms.ScrollBars]::Both
$script:Output.WordWrap = $false
$script:Output.BackColor = [System.Drawing.Color]::White
$script:Output.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10)
$script:Output.Text = "欢迎使用 G+ 测试助手。`r`n`r`n官方演练：填写当前案例编号，勾选页面核对，再点击开始。`r`n本地测试：选择「本地模拟测试」页签，保留默认种子即可运行。`r`n`r`n结果保存位置：$script:ResultsPath"
$script:Form.Controls.Add($script:Output)

$officialButton.Add_Click({
    $teamValue = $teamBox.Text.Trim()
    $caseValue = $caseBox.Text.Trim().ToUpperInvariant()
    $portValue = 0
    if ([string]::IsNullOrWhiteSpace($teamValue)) {
        Show-InputError '请填写官方模拟器当前登录的参赛队号。'
        return
    }
    if (-not [int]::TryParse($portBox.Text.Trim(), [ref]$portValue) -or $portValue -lt 1 -or $portValue -gt 65535) {
        Show-InputError '接口端口应为 1 到 65535 的整数，默认是 2026。'
        return
    }
    if ($caseValue -cnotmatch '^[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3}$') {
        Show-InputError '请从当前官方演练页面复制案例编号，格式为 XXXX-XXXX-XXXX-XXXX。'
        return
    }
    if (-not $readyCheck.Checked) {
        Show-InputError '请先核对当前页面为“问题3演练测试”，并等待倒计时结束、接口开放，再勾选核对框。'
        return
    }
    $caseBox.Text = $caseValue
    Start-Test 'G+ 官方演练' @('--official', '--team', $teamValue, '--port', [string]$portValue,
        '--case', $caseValue, '--title', '问题3演练测试', '--ready')
})
$localButton.Add_Click({
    $seedValue = 0L
    if (-not [long]::TryParse($seedBox.Text.Trim(), [ref]$seedValue)) {
        Show-InputError '随机种子应为整数，例如 13001。'
        return
    }
    $options = @('--local', '--seed', [string]$seedValue)
    $label = 'G+ 本地测试'
    if ($baselineCheck.Checked) {
        $options += '--baseline'
        $label = 'G 基线本地测试'
    }
    Start-Test $label $options
})
$checkButton.Add_Click({ Start-Test '运行环境检查' @('--check') })
$resultsButton.Add_Click({
    try {
        [void][System.IO.Directory]::CreateDirectory($script:ResultsPath)
        $openInfo = New-Object System.Diagnostics.ProcessStartInfo
        $openInfo.FileName = $script:ResultsPath
        $openInfo.UseShellExecute = $true
        [void][System.Diagnostics.Process]::Start($openInfo)
    } catch { Show-InputError "无法打开结果目录：$($_.Exception.Message)" }
})

$script:Timer = New-Object System.Windows.Forms.Timer
$script:Timer.Interval = 250
$script:Timer.Add_Tick({
    if ($null -eq $script:RunProcess) { return }
    try {
        $elapsed = [int]([DateTime]::Now - $script:StartedAt).TotalSeconds
        $script:Status.Text = "$script:RunLabel · 已运行 $elapsed 秒"
        if (-not $script:RunProcess.HasExited) { return }
        $script:Timer.Stop()
        $script:RunProcess.WaitForExit()
        $stdout = $script:OutputTask.GetAwaiter().GetResult()
        $stderr = $script:ErrorTask.GetAwaiter().GetResult()
        $exitCode = $script:RunProcess.ExitCode
        $script:LastExitCode = $exitCode
        $message = $stdout.TrimEnd()
        if (-not [string]::IsNullOrWhiteSpace($stderr)) {
            $message += "`r`n`r`n程序信息：`r`n" + $stderr.TrimEnd()
        }
        if ([string]::IsNullOrWhiteSpace($message)) { $message = "程序已结束，返回状态：$exitCode。" }
        $script:Output.Text = $message -replace '(?<!\r)\n', "`r`n"
        $script:Output.SelectionStart = 0
        $script:Output.ScrollToCaret()
        $state = if ($exitCode -eq 0) { '已完成' } elseif ($exitCode -eq 2) { '输入需调整' } else { '未完成，请查看结果' }
        $script:Status.Text = "$script:RunLabel · $state · $elapsed 秒"
        $script:RunProcess.Dispose()
        $script:RunProcess = $null
        $script:OutputTask = $null
        $script:ErrorTask = $null
        $readyCheck.Checked = $false
        Set-Busy $false
    } catch {
        $script:Timer.Stop()
        $script:Output.AppendText("`r`n界面读取结果时出错：$($_.Exception.Message)`r`n测试进程仍由本窗口管理，请关闭窗口时选择等待或停止。")
        $script:Status.Text = '读取结果出错'
    }
})
$script:Form.Add_FormClosing({
    param($sender, $eventArgs)
    if ($null -eq $script:RunProcess) { return }
    if ($script:RunProcess.HasExited) {
        $script:RunProcess.Dispose()
        $script:RunProcess = $null
        return
    }
    $choice = [System.Windows.Forms.MessageBox]::Show(
        $script:Form,
        "测试仍在运行。`r`n`r`n选择「否」继续等待；选择「是」停止测试并关闭。`r`n停止官方演练后，同一案例不要重复运行，已发送的动作无法撤回。",
        '是否停止正在运行的测试？',
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question,
        [System.Windows.Forms.MessageBoxDefaultButton]::Button2)
    if ($choice -ne [System.Windows.Forms.DialogResult]::Yes) {
        $eventArgs.Cancel = $true
        return
    }
    try {
        # Stop descendants too, so a local test cannot outlive this window.
        $stopInfo = New-Object System.Diagnostics.ProcessStartInfo
        $stopInfo.FileName = Join-Path $env:SystemRoot 'System32\taskkill.exe'
        $stopInfo.Arguments = '/PID ' + $script:RunProcess.Id + ' /T /F'
        $stopInfo.UseShellExecute = $false
        $stopInfo.CreateNoWindow = $true
        $stopInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $stopProcess = [System.Diagnostics.Process]::Start($stopInfo)
        [void]$stopProcess.WaitForExit(5000)
        $stopProcess.Dispose()
        if (-not $script:RunProcess.WaitForExit(1000)) { throw '测试仍未停止。请保留此窗口，再尝试关闭。' }
        $script:Timer.Stop()
        $script:RunProcess.Dispose()
        $script:RunProcess = $null
    } catch {
        $eventArgs.Cancel = $true
        Show-InputError "停止测试失败：$($_.Exception.Message)"
    }
})

try {
    if ($SelfCheck) {
        if ([string]::IsNullOrWhiteSpace($PreviewPath)) {
            $PreviewPath = Join-Path $env:TEMP 'q3_gplus_test_helper_preview.png'
        }
        if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw "Python 文件不存在：$PythonPath" }
        if (-not (Test-Path -LiteralPath $script:BackendPath -PathType Leaf)) { throw "Python 测试后端不存在：$script:BackendPath" }
        # An invisible shown form creates every child handle for a real render.
        $script:Form.ShowInTaskbar = $false
        $script:Form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
        $script:Form.Location = New-Object System.Drawing.Point(-32000, -32000)
        $script:Form.Opacity = 0
        $script:Form.Show()
        [System.Windows.Forms.Application]::DoEvents()
        Start-Test '运行环境检查' @('--check')
        $checkDeadline = [DateTime]::Now.AddSeconds(20)
        while ($null -ne $script:RunProcess -and [DateTime]::Now -lt $checkDeadline) {
            [System.Windows.Forms.Application]::DoEvents()
            [System.Threading.Thread]::Sleep(25)
        }
        if ($null -ne $script:RunProcess) { throw 'GUI 环境检查超过 20 秒，未正常结束。' }
        if ($script:LastExitCode -ne 0 -or -not $script:Output.Text.Contains('检查通过')) {
            throw ('GUI 环境检查未通过：' + $script:Output.Text)
        }
        if (-not $officialButton.Enabled -or -not $checkButton.Enabled -or $readyCheck.Checked) {
            throw 'GUI 运行后的按钮状态异常。'
        }
        $script:Form.PerformLayout()
        $image = New-Object System.Drawing.Bitmap($script:Form.Width, $script:Form.Height)
        try {
            $rectangle = New-Object System.Drawing.Rectangle(0, 0, $script:Form.Width, $script:Form.Height)
            $script:Form.DrawToBitmap($image, $rectangle)
            $image.Save($PreviewPath, [System.Drawing.Imaging.ImageFormat]::Png)
        } finally { $image.Dispose() }
        $script:Form.Hide()
        [Console]::WriteLine('GUI_SELF_CHECK_OK')
        [Console]::WriteLine('GUI_PROCESS_CHECK_OK: UTF-8 output, timer, exit 0 and button reset')
        [Console]::WriteLine($PreviewPath)
    } else {
        [void]$script:Form.ShowDialog()
    }
} catch {
    if ($SelfCheck) { [Console]::Error.WriteLine($_.ScriptStackTrace) }
    throw
} finally {
    if ($SelfCheck -and $null -ne $script:RunProcess) {
        if (-not $script:RunProcess.HasExited) {
            $script:RunProcess.Kill()
            [void]$script:RunProcess.WaitForExit(2000)
        }
        $script:RunProcess.Dispose()
        $script:RunProcess = $null
    }
    $script:Timer.Dispose()
    $script:Form.Dispose()
}
