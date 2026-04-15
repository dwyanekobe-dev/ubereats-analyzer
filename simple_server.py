#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import http.server
import socketserver
import sqlite3
import json
import os
import uuid
from datetime import datetime
import webbrowser
import threading
import time

PORT = int(os.environ.get('PORT', 8000))
DB_FILE = 'ubereats_orders.db'
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

class UberEatsHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.serve_main_page()
        elif self.path == '/api/orders':
            self.serve_orders()
        elif self.path == '/api/stats':
            self.serve_stats()
        elif self.path == '/api/uploads':
            self.serve_uploads()
        elif self.path.startswith('/uploads/'):
            self.serve_uploaded_file()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/orders':
            self.add_order()
        elif self.path == '/api/upload':
            self.handle_upload()
        elif self.path == '/api/delete-upload':
            self.delete_upload()
        else:
            self.send_error(404)

    def serve_main_page(self):
        html_content = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UberEats 消費分析系統</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Microsoft JhengHei', sans-serif;
        }
        .main-container {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            margin: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .stats-card {
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
            color: white;
            text-align: center;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            transition: transform 0.3s ease;
        }
        .stats-card:hover { transform: translateY(-5px); }
        .stats-number { font-size: 2.5rem; font-weight: bold; margin: 10px 0; }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 25px;
        }
        .upload-zone {
            border: 3px dashed #667eea;
            border-radius: 15px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #f8f9ff;
        }
        .upload-zone:hover, .upload-zone.dragover {
            background: #eef0ff;
            border-color: #764ba2;
            transform: scale(1.01);
        }
        .upload-zone h4 { color: #667eea; margin-bottom: 10px; }
        .upload-zone p { color: #999; margin: 0; }
        .preview-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .preview-item {
            position: relative;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        .preview-item:hover { transform: translateY(-3px); }
        .preview-item img {
            width: 100%;
            height: 200px;
            object-fit: cover;
        }
        .preview-item .info {
            padding: 10px;
            background: white;
            font-size: 0.85rem;
        }
        .preview-item .delete-btn {
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgba(220, 53, 69, 0.9);
            color: white;
            border: none;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            cursor: pointer;
            font-size: 14px;
            line-height: 30px;
            text-align: center;
        }
        .upload-progress {
            display: none;
            margin-top: 15px;
        }
        .upload-count {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            text-align: center;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
        }
        .upload-count .stats-number { font-size: 2.5rem; font-weight: bold; margin: 10px 0; }
        .nav-tabs .nav-link { color: #667eea; }
        .nav-tabs .nav-link.active { color: #764ba2; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="main-container">
            <div class="text-center mb-5">
                <h1 class="display-4">UberEats 消費分析系統</h1>
                <p class="lead text-muted">追蹤您的美食消費，分析用餐習慣</p>
            </div>

            <!-- 統計卡片 -->
            <div class="row mb-4">
                <div class="col-md-3 mb-3">
                    <div class="stats-card">
                        <div class="stats-number" id="totalOrders">0</div>
                        <div>總訂單數</div>
                    </div>
                </div>
                <div class="col-md-3 mb-3">
                    <div class="stats-card">
                        <div class="stats-number" id="totalAmount">$0</div>
                        <div>總消費金額</div>
                    </div>
                </div>
                <div class="col-md-3 mb-3">
                    <div class="stats-card">
                        <div class="stats-number" id="avgAmount">$0</div>
                        <div>平均金額</div>
                    </div>
                </div>
                <div class="col-md-3 mb-3">
                    <div class="upload-count">
                        <div class="stats-number" id="uploadCount">0</div>
                        <div>已上傳截圖</div>
                    </div>
                </div>
            </div>

            <!-- 分頁 -->
            <ul class="nav nav-tabs mb-4" role="tablist">
                <li class="nav-item">
                    <a class="nav-link active" data-bs-toggle="tab" href="#uploadTab">截圖上傳</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" data-bs-toggle="tab" href="#manualTab">手動新增</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" data-bs-toggle="tab" href="#recordTab">訂單記錄</a>
                </li>
            </ul>

            <div class="tab-content">
                <!-- 截圖上傳 -->
                <div class="tab-pane fade show active" id="uploadTab">
                    <div class="card mb-4">
                        <div class="card-header" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white;">
                            <h3 class="mb-0">上傳 UberEats 訂單截圖</h3>
                        </div>
                        <div class="card-body">
                            <div class="upload-zone" id="uploadZone" onclick="document.getElementById('fileInput').click()">
                                <h4>點擊上傳截圖</h4>
                                <p>支援 JPG、PNG 格式，可一次上傳多張</p>
                                <p style="margin-top: 10px; color: #667eea;">從手機 Uber Eats App 的訂單頁面截圖即可</p>
                            </div>
                            <input type="file" id="fileInput" accept="image/*" multiple style="position:absolute;left:-9999px;">
                            <label for="fileInput" class="btn btn-primary btn-lg w-100 mt-3" style="border-radius:15px;">選擇相片上傳</label>

                            <div class="upload-progress" id="uploadProgress">
                                <div class="progress">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated"
                                         id="progressBar" style="width: 0%"></div>
                                </div>
                                <p class="text-center mt-2" id="progressText">上傳中...</p>
                            </div>

                            <div class="preview-grid" id="previewGrid"></div>
                        </div>
                    </div>
                </div>

                <!-- 手動新增 -->
                <div class="tab-pane fade" id="manualTab">
                    <div class="card mb-4">
                        <div class="card-header bg-primary text-white">
                            <h3 class="mb-0">手動新增訂單</h3>
                        </div>
                        <div class="card-body">
                            <form id="orderForm">
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <label class="form-label">餐廳名稱</label>
                                        <input type="text" class="form-control" id="restaurantName" required
                                               placeholder="例：麥當勞、肯德基、星巴克">
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <label class="form-label">訂單日期</label>
                                        <input type="date" class="form-control" id="orderDate" required>
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <label class="form-label">金額 (NT$)</label>
                                        <input type="number" step="1" class="form-control" id="amount" required
                                               placeholder="150">
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <label class="form-label">餐點項目</label>
                                        <input type="text" class="form-control" id="items" required
                                               placeholder="例：大麥克餐、薯條、可樂">
                                    </div>
                                </div>
                                <button type="submit" class="btn btn-primary btn-lg">新增訂單</button>
                            </form>
                        </div>
                    </div>
                </div>

                <!-- 訂單記錄 -->
                <div class="tab-pane fade" id="recordTab">
                    <div class="card">
                        <div class="card-header bg-secondary text-white">
                            <h3 class="mb-0">訂單記錄</h3>
                        </div>
                        <div class="card-body">
                            <div class="table-responsive">
                                <table class="table table-striped table-hover">
                                    <thead class="table-dark">
                                        <tr>
                                            <th>餐廳</th>
                                            <th>日期</th>
                                            <th>金額</th>
                                            <th>餐點</th>
                                        </tr>
                                    </thead>
                                    <tbody id="ordersTable"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('orderDate').value = new Date().toISOString().split('T')[0];
            loadStats();
            loadOrders();
            loadUploads();
            document.getElementById('orderForm').addEventListener('submit', handleSubmit);
            setupUpload();
        });

        // === 上傳功能 ===
        function setupUpload() {
            var zone = document.getElementById('uploadZone');
            var input = document.getElementById('fileInput');

            input.addEventListener('change', function() {
                if (input.files.length > 0) uploadFiles(input.files);
            });

            zone.addEventListener('dragover', function(e) {
                e.preventDefault();
                zone.classList.add('dragover');
            });
            zone.addEventListener('dragleave', function() {
                zone.classList.remove('dragover');
            });
            zone.addEventListener('drop', function(e) {
                e.preventDefault();
                zone.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) uploadFiles(e.dataTransfer.files);
            });
        }

        var localUploads = [];

        async function uploadFiles(files) {
            var progress = document.getElementById('uploadProgress');
            var bar = document.getElementById('progressBar');
            var text = document.getElementById('progressText');
            progress.style.display = 'block';

            var total = files.length;
            var done = 0;

            for (var i = 0; i < files.length; i++) {
                var file = files[i];
                text.textContent = '處理中 (' + (i+1) + '/' + total + '): ' + file.name;
                bar.style.width = ((i / total) * 100) + '%';

                // 用 FileReader 在瀏覽器端讀取圖片
                var dataUrl = await new Promise(function(resolve) {
                    var reader = new FileReader();
                    reader.onload = function(e) { resolve(e.target.result); };
                    reader.readAsDataURL(file);
                });

                localUploads.push({
                    name: file.name,
                    size: file.size > 1024*1024 ? (file.size/1024/1024).toFixed(1)+' MB' : Math.round(file.size/1024)+' KB',
                    dataUrl: dataUrl
                });

                // 也嘗試上傳到伺服器（如果失敗也沒關係）
                try {
                    var formData = new FormData();
                    formData.append('file', file);
                    await fetch('/api/upload', { method: 'POST', body: formData });
                } catch (err) {}

                done++;
            }

            bar.style.width = '100%';
            text.textContent = '完成！已處理 ' + done + ' 張截圖';
            setTimeout(function() { progress.style.display = 'none'; }, 2000);

            document.getElementById('fileInput').value = '';
            renderUploads();
        }

        function renderUploads() {
            var grid = document.getElementById('previewGrid');
            grid.innerHTML = '';
            document.getElementById('uploadCount').textContent = localUploads.length;

            localUploads.forEach(function(file, idx) {
                var div = document.createElement('div');
                div.className = 'preview-item';
                var img = document.createElement('img');
                img.src = file.dataUrl;
                img.alt = 'screenshot';
                div.appendChild(img);
                var btn = document.createElement('button');
                btn.className = 'delete-btn';
                btn.textContent = 'X';
                btn.onclick = function() { localUploads.splice(idx, 1); renderUploads(); };
                div.appendChild(btn);
                var info = document.createElement('div');
                info.className = 'info';
                info.innerHTML = '<div>' + file.name + '</div><div style="color:#999">' + file.size + '</div>';
                div.appendChild(info);
                grid.appendChild(div);
            });
        }

        async function loadUploads() {
            // 顯示本地預覽
            renderUploads();
            // 也嘗試載入伺服器端的（如果有的話）
            try {
                var response = await fetch('/api/uploads');
                var uploads = await response.json();
                if (uploads.length > 0 && localUploads.length === 0) {
                    document.getElementById('uploadCount').textContent = uploads.length;
                    var grid = document.getElementById('previewGrid');
                    uploads.forEach(function(file) {
                        var div = document.createElement('div');
                        div.className = 'preview-item';
                        div.innerHTML =
                            '<img src="/uploads/' + file.name + '" alt="screenshot">' +
                            '<div class="info"><div>' + file.name + '</div><div style="color:#999">' + file.size + '</div></div>';
                        grid.appendChild(div);
                    });
                }
            } catch (err) {}
        }

        async function deleteUpload(filename) {
            if (!confirm('確定要刪除這張截圖嗎？')) return;
            try {
                await fetch('/api/delete-upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: filename })
                });
                loadUploads();
            } catch (err) {
                console.error('Delete failed:', err);
            }
        }

        // === 訂單功能 ===
        async function handleSubmit(e) {
            e.preventDefault();
            var formData = {
                restaurant_name: document.getElementById('restaurantName').value,
                order_date: document.getElementById('orderDate').value,
                amount: parseInt(document.getElementById('amount').value),
                items: document.getElementById('items').value
            };
            try {
                var response = await fetch('/api/orders', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
                if (response.ok) {
                    document.getElementById('orderForm').reset();
                    document.getElementById('orderDate').value = new Date().toISOString().split('T')[0];
                    loadStats();
                    loadOrders();
                    alert('訂單新增成功！');
                } else {
                    alert('新增失敗，請重試');
                }
            } catch (error) {
                alert('新增失敗：' + error.message);
            }
        }

        async function loadStats() {
            try {
                var response = await fetch('/api/stats');
                var stats = await response.json();
                document.getElementById('totalOrders').textContent = stats.total_orders;
                document.getElementById('totalAmount').textContent = '$' + Math.round(stats.total_amount);
                document.getElementById('avgAmount').textContent = '$' + Math.round(stats.avg_amount);
            } catch (error) {
                console.error('載入統計失敗:', error);
            }
        }

        async function loadOrders() {
            try {
                var response = await fetch('/api/orders');
                var orders = await response.json();
                var tableBody = document.getElementById('ordersTable');
                tableBody.innerHTML = '';
                orders.forEach(function(order) {
                    var row = document.createElement('tr');
                    row.innerHTML =
                        '<td><strong>' + order.restaurant_name + '</strong></td>' +
                        '<td>' + new Date(order.order_date).toLocaleDateString('zh-TW') + '</td>' +
                        '<td><span class="badge bg-success">$' + order.amount + '</span></td>' +
                        '<td>' + order.items + '</td>';
                    tableBody.appendChild(row);
                });
            } catch (error) {
                console.error('載入訂單失敗:', error);
            }
        }
    </script>
</body>
</html>'''

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(html_content.encode('utf-8')))
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))

    def handle_upload(self):
        try:
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_error_response('Invalid content type')
                return

            # 解析 boundary
            boundary = content_type.split('boundary=')[1].strip()
            if boundary.startswith('"') and boundary.endswith('"'):
                boundary = boundary[1:-1]

            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)

            # 解析 multipart 資料
            boundary_bytes = boundary.encode()
            parts = body.split(b'--' + boundary_bytes)

            for part in parts:
                if b'filename="' not in part:
                    continue

                # 取得檔名
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue
                header = part[:header_end].decode('utf-8', errors='replace')
                file_data = part[header_end + 4:]
                if file_data.endswith(b'\r\n'):
                    file_data = file_data[:-2]

                # 取得原始檔名
                import re
                fname_match = re.search(r'filename="([^"]+)"', header)
                if not fname_match:
                    continue
                original_name = fname_match.group(1)

                # 取得副檔名
                ext = os.path.splitext(original_name)[1].lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    ext = '.jpg'

                # 產生唯一檔名
                filename = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + str(uuid.uuid4())[:8] + ext
                filepath = os.path.join(UPLOAD_DIR, filename)

                with open(filepath, 'wb') as f:
                    f.write(file_data)

                response = json.dumps({
                    'success': True,
                    'filename': filename,
                    'size': len(file_data)
                }, ensure_ascii=False)
                self.send_json_response(response)
                return

            self.send_error_response('No file found in request')

        except Exception as e:
            self.send_error_response(str(e))

    def serve_uploads(self):
        try:
            files = []
            for f in sorted(os.listdir(UPLOAD_DIR), reverse=True):
                filepath = os.path.join(UPLOAD_DIR, f)
                if os.path.isfile(filepath):
                    size = os.path.getsize(filepath)
                    if size > 1024 * 1024:
                        size_str = '{:.1f} MB'.format(size / (1024 * 1024))
                    else:
                        size_str = '{:.0f} KB'.format(size / 1024)
                    files.append({'name': f, 'size': size_str})
            response = json.dumps(files, ensure_ascii=False)
            self.send_json_response(response)
        except Exception as e:
            self.send_error_response(str(e))

    def serve_uploaded_file(self):
        try:
            filename = self.path.split('/uploads/')[1]
            # 安全檢查：防止路徑遍歷
            filename = os.path.basename(filename)
            filepath = os.path.join(UPLOAD_DIR, filename)

            if not os.path.isfile(filepath):
                self.send_error(404)
                return

            ext = os.path.splitext(filename)[1].lower()
            content_types = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            content_type = content_types.get(ext, 'application/octet-stream')

            with open(filepath, 'rb') as f:
                data = f.read()

            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(data))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500)

    def delete_upload(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            filename = os.path.basename(data.get('filename', ''))
            filepath = os.path.join(UPLOAD_DIR, filename)

            if os.path.isfile(filepath):
                os.remove(filepath)
                response = json.dumps({'success': True}, ensure_ascii=False)
            else:
                response = json.dumps({'success': False, 'error': 'File not found'}, ensure_ascii=False)
            self.send_json_response(response)
        except Exception as e:
            self.send_error_response(str(e))

    def serve_orders(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('SELECT id, restaurant_name, order_date, amount, items FROM orders ORDER BY order_date DESC')
            orders = cursor.fetchall()
            conn.close()
            orders_list = [{'id': o[0], 'restaurant_name': o[1], 'order_date': o[2], 'amount': o[3], 'items': o[4]} for o in orders]
            response = json.dumps(orders_list, ensure_ascii=False)
            self.send_json_response(response)
        except Exception as e:
            self.send_error_response(str(e))

    def serve_stats(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*), SUM(amount), AVG(amount) FROM orders')
            total_orders, total_amount, avg_amount = cursor.fetchone()
            conn.close()
            stats = {
                'total_orders': total_orders or 0,
                'total_amount': float(total_amount) if total_amount else 0,
                'avg_amount': float(avg_amount) if avg_amount else 0,
            }
            response = json.dumps(stats, ensure_ascii=False)
            self.send_json_response(response)
        except Exception as e:
            self.send_error_response(str(e))

    def add_order(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO orders (restaurant_name, order_date, amount, items) VALUES (?, ?, ?, ?)',
                           (data['restaurant_name'], data['order_date'], int(data['amount']), data['items']))
            conn.commit()
            order_id = cursor.lastrowid
            conn.close()
            response = json.dumps({'success': True, 'id': order_id}, ensure_ascii=False)
            self.send_json_response(response)
        except Exception as e:
            self.send_error_response(str(e))

    def send_json_response(self, response):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(response.encode('utf-8')))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

    def send_error_response(self, error):
        response = json.dumps({'success': False, 'error': error}, ensure_ascii=False)
        self.send_response(500)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(response.encode('utf-8')))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

    def log_message(self, format, *args):
        pass  # 靜音 log


def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_name TEXT NOT NULL,
            order_date DATE NOT NULL,
            amount INTEGER NOT NULL,
            items TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('SELECT COUNT(*) FROM orders')
    count = cursor.fetchone()[0]
    if count == 0:
        orders = [
            ('臭名昭彰祖傳酥炸臭豆腐', '2026-04-06', 130, '臭豆腐'),
            ('串本町串燒（原火奴總店）', '2026-03-22', 417, '8份餐點'),
            ('阿俊龍飽', '2026-03-14', 130, '蝦仁炒飯'),
            ('肉蛋吐司創始店 肉蛋中西式早餐店', '2026-03-14', 170, '招牌肉蛋土司、招牌冰奶茶'),
            ('范姜雞肉飯 后里甲后店', '2026-03-09', 166, 'Braised Chicken Rice、Pork Meatballs Soup、Braised Tofu'),
            ('鍋裡GOiN風味湯鍋 台中后里店', '2026-02-26', 226, '火鍋美食鍋'),
            ('一頂燒堡臭豆腐 后里店', '2026-02-11', 140, '酥炸臭豆腐'),
        ]
        cursor.executemany('INSERT INTO orders (restaurant_name, order_date, amount, items) VALUES (?, ?, ?, ?)', orders)
        print('已載入 7 筆 UberEats 訂單')
    conn.commit()
    conn.close()


def open_browser():
    time.sleep(2)
    webbrowser.open('http://localhost:{}'.format(PORT))


def main():
    print("UberEats 消費分析系統啟動中...")
    init_database()
    print("上傳資料夾: {}".format(UPLOAD_DIR))
    try:
        with socketserver.TCPServer(("", PORT), UberEatsHandler) as httpd:
            print("伺服器已啟動：http://localhost:{}".format(PORT))
            print("按 Ctrl+C 停止伺服器")
            if not os.environ.get('RAILWAY_ENVIRONMENT'):
                browser_thread = threading.Thread(target=open_browser)
                browser_thread.daemon = True
                browser_thread.start()
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已停止")
    except OSError as e:
        if "Address already in use" in str(e) or "10048" in str(e):
            print("端口 {} 已被佔用，請關閉其他程式或改用其他端口".format(PORT))
        else:
            print("啟動失敗：{}".format(e))


if __name__ == "__main__":
    main()
