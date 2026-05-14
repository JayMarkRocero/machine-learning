<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

// ── Configuration ──────────────────────────────────────────
// Auto-detect Python path
$possible_python_paths = [
    'C:/Program Files/Python313/python.exe',
    'C:/Program Files/Python312/python.exe',
    'C:/Program Files/Python311/python.exe',
    'C:/Users/rocer/AppData/Roaming/Python/Python313/Scripts/python.exe',
    'python',
    'python3',
];

$python = null;
foreach ($possible_python_paths as $path) {
    if (file_exists($path) || $path === 'python' || $path === 'python3') {
        $python = $path;
        break;
    }
}

if (!$python) {
    echo json_encode([
        'status'  => 'error',
        'message' => 'Python executable not found. Check your Python installation.'
    ]);
    exit;
}

// Auto-detect script path based on this file's location
$base_dir = dirname(dirname(__FILE__)); // goes up from /api/ to project root
$script   = $base_dir . '/python/run_all_forecasts.py';

// Normalize path separators for Windows
$script = str_replace('\\', '/', $script);
$python = str_replace('\\', '/', $python);

// ── Validate script exists ─────────────────────────────────
if (!file_exists($script)) {
    echo json_encode([
        'status'  => 'error',
        'message' => 'Python script not found at: ' . $script,
        'tip'     => 'Make sure run_all_forecasts.py is in the python/ folder'
    ]);
    exit;
}

// ── Build and run command ──────────────────────────────────
$cmd    = "\"$python\" \"$script\" 2>&1";
$output = shell_exec($cmd);

if ($output === null || $output === '') {
    // Try alternative execution method
    $descriptors = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w'],
    ];

    $process = proc_open($cmd, $descriptors, $pipes);

    if (is_resource($process)) {
        fclose($pipes[0]);
        $output  = stream_get_contents($pipes[1]);
        $errors  = stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);
        proc_close($process);
        $output = $output . $errors;
    }
}

// ── Return result ──────────────────────────────────────────
if ($output === null || trim($output) === '') {
    echo json_encode([
        'status'  => 'error',
        'message' => 'Script produced no output. PHP may not have permission to run Python.',
        'debug'   => [
            'python' => $python,
            'script' => $script,
            'cmd'    => $cmd
        ]
    ]);
} else if (str_contains($output, 'Error') || str_contains($output, 'Traceback')) {
    echo json_encode([
        'status'  => 'error',
        'message' => 'Forecast script encountered an error.',
        'log'     => $output,
        'debug'   => [
            'python' => $python,
            'script' => $script
        ]
    ]);
} else {
    echo json_encode([
        'status'  => 'success',
        'message' => 'Forecast completed successfully!',
        'log'     => $output,
        'run_at'  => date('Y-m-d H:i:s'),
        'debug'   => [
            'python' => $python,
            'script' => $script
        ]
    ]);
}