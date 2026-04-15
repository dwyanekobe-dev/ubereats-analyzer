#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import http.server
import socketserver
import sqlite3
import json
import os
import uuid
import base64
import urllib.request
import urllib.error
from datetime import datetime
import webbrowser
import threading
import time

PORT = int(os.environ.get('PORT', 8000))
DB_FILE = 'ubereats_orders.db'
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
os.makedirs(UPLOAD_DIR, exist_ok=True)

def recognize_orders(image_data, media_type='image/jpeg'):
    """用 Claude Vision API 辨識 UberEats 截圖中的訂單"""
    if not ANTHROPIC_API_KEY:
        print('ANTHROPIC_API_KEY not set, skipping OCR')
        return []

    img_b64 = base64.b64encode(image_data).decode('utf-8')

    request_body = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2048,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": img_b64
                    }
                },
                {
                    "type": "text",
                    "text": '這是 UberEats 訂單截圖，請辨識所有訂單，回傳 JSON 陣列。每筆訂單格式：{"restaurant_name":"店名","order_date":"YYYY-MM-DD","amount":金額數字,"items":"餐點描述"}。只回傳 JSON 陣列，不要其他文字。如果看不到訂單就回傳 []。日期如果只顯示月日，年份請用 2026。金額只取數字（不含$符號）。'
                }
            ]
        }]
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=request_body,
        headers={
            'Content-Type': 'application/json',
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01'
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            text = result['content'][0]['text'].strip()
            # 找到 JSON 陣列部分
            start = text.find('[')
            end = text.rfind(']') + 1
            if start >= 0 and end > start:
                orders = json.loads(text[start:end])
                print('Claude 辨識到 {} 筆訂單'.format(len(orders)))
                return orders
            return []
    except Exception as e:
        print('Claude Vision API error: {}'.format(e))
        return []


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
        elif self.path == '/api/orders/update':
            self.update_order()
        elif self.path == '/api/orders/delete':
            self.delete_order()
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
                            <div class="upload-zone" id="uploadZone">
                                <h4>點擊下方按鈕上傳截圖</h4>
                                <p>支援 JPG、PNG 格式，可一次上傳多張</p>
                                <p style="margin-top: 10px; color: #667eea;">從手機 Uber Eats App 的訂單頁面截圖即可</p>
                            </div>
                            <input type="file" id="fileInput" accept="image/*" multiple
                                   style="display:block;width:100%;padding:15px;margin-top:15px;font-size:18px;border:2px solid #667eea;border-radius:15px;background:#f8f9ff;"
                                   onchange="handleFiles(this)">

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
                                            <th style="width:120px">操作</th>
                                        </tr>
                                    </thead>
                                    <tbody id="ordersTable"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>

            <!-- 編輯 Modal -->
            <div class="modal fade" id="editModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header" style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;">
                            <h5 class="modal-title">編輯訂單</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <input type="hidden" id="editId">
                            <div class="mb-3">
                                <label class="form-label">餐廳名稱</label>
                                <input type="text" class="form-control" id="editRestaurant" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">訂單日期</label>
                                <input type="date" class="form-control" id="editDate" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">金額 (NT$)</label>
                                <input type="number" class="form-control" id="editAmount" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">餐點項目</label>
                                <input type="text" class="form-control" id="editItems" required>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-primary" onclick="saveEdit()">儲存</button>
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
            document.getElementById('orderForm').addEventListener('submit', handleSubmit);
        });

        // === 上傳功能 ===
        function handleFiles(input) {
            if (!input.files || input.files.length === 0) return;
            var grid = document.getElementById('previewGrid');

            for (var i = 0; i < input.files.length; i++) {
                (function(file) {
                    var url = URL.createObjectURL(file);
                    var div = document.createElement('div');
                    div.className = 'preview-item';
                    div.innerHTML =
                        '<img src="' + url + '" alt="screenshot">' +
                        '<div class="info" style="background:#fff3cd;color:#856404;"><div>AI 辨識中...</div></div>';
                    grid.appendChild(div);

                    // 送到伺服器做 AI 辨識
                    var formData = new FormData();
                    formData.append('file', file);
                    fetch('/api/upload', { method: 'POST', body: formData })
                        .then(function(r) { return r.json(); })
                        .then(function(result) {
                            var info = div.querySelector('.info');
                            if (result.success && result.message) {
                                info.style.background = '#d4edda';
                                info.style.color = '#155724';
                                info.innerHTML = '<div>' + result.message + '</div>';
                                if (result.added && result.added.length > 0) {
                                    info.innerHTML += '<div style="font-size:0.8rem;margin-top:4px;">新增：' + result.added.join('、') + '</div>';
                                }
                                if (result.skipped && result.skipped.length > 0) {
                                    info.innerHTML += '<div style="font-size:0.8rem;color:#856404;">重複跳過：' + result.skipped.join('、') + '</div>';
                                }
                                loadStats();
                                loadOrders();
                            } else {
                                info.style.background = '#f8d7da';
                                info.style.color = '#721c24';
                                info.innerHTML = '<div>辨識失敗</div>';
                            }
                        })
                        .catch(function() {
                            var info = div.querySelector('.info');
                            info.style.background = '#f8d7da';
                            info.style.color = '#721c24';
                            info.innerHTML = '<div>上傳失敗</div>';
                        });
                })(input.files[i]);
            }

            document.getElementById('uploadCount').textContent =
                parseInt(document.getElementById('uploadCount').textContent || '0') + input.files.length;
            input.value = '';
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
                var result = await response.json();
                if (result.duplicate) {
                    alert('此訂單已存在（同餐廳、同日期、同金額），不會重複新增');
                    return;
                }
                if (result.success) {
                    document.getElementById('orderForm').reset();
                    document.getElementById('orderDate').value = new Date().toISOString().split('T')[0];
                    loadStats();
                    loadOrders();
                    alert('訂單新增成功！');
                } else {
                    alert('新增失敗：' + (result.error || '請重試'));
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

        var allOrders = [];

        async function loadOrders() {
            try {
                var response = await fetch('/api/orders');
                allOrders = await response.json();
                var tableBody = document.getElementById('ordersTable');
                tableBody.innerHTML = '';
                allOrders.forEach(function(order, idx) {
                    var row = document.createElement('tr');
                    var td1 = document.createElement('td');
                    td1.innerHTML = '<strong>' + order.restaurant_name + '</strong>';
                    var td2 = document.createElement('td');
                    td2.textContent = new Date(order.order_date).toLocaleDateString('zh-TW');
                    var td3 = document.createElement('td');
                    td3.innerHTML = '<span class="badge bg-success">$' + order.amount + '</span>';
                    var td4 = document.createElement('td');
                    td4.textContent = order.items;
                    var td5 = document.createElement('td');
                    var editBtn = document.createElement('button');
                    editBtn.className = 'btn btn-sm btn-outline-primary me-1';
                    editBtn.textContent = '編輯';
                    editBtn.setAttribute('data-idx', idx);
                    editBtn.onclick = function() { openEdit(parseInt(this.getAttribute('data-idx'))); };
                    var delBtn = document.createElement('button');
                    delBtn.className = 'btn btn-sm btn-outline-danger';
                    delBtn.textContent = '刪除';
                    delBtn.setAttribute('data-id', order.id);
                    delBtn.onclick = function() { deleteOrder(parseInt(this.getAttribute('data-id'))); };
                    td5.appendChild(editBtn);
                    td5.appendChild(delBtn);
                    row.appendChild(td1);
                    row.appendChild(td2);
                    row.appendChild(td3);
                    row.appendChild(td4);
                    row.appendChild(td5);
                    tableBody.appendChild(row);
                });
            } catch (error) {
                console.error('載入訂單失敗:', error);
            }
        }

        function openEdit(idx) {
            var order = allOrders[idx];
            document.getElementById('editId').value = order.id;
            document.getElementById('editRestaurant').value = order.restaurant_name;
            document.getElementById('editDate').value = order.order_date;
            document.getElementById('editAmount').value = order.amount;
            document.getElementById('editItems').value = order.items;
            new bootstrap.Modal(document.getElementById('editModal')).show();
        }

        async function saveEdit() {
            var data = {
                id: document.getElementById('editId').value,
                restaurant_name: document.getElementById('editRestaurant').value,
                order_date: document.getElementById('editDate').value,
                amount: parseInt(document.getElementById('editAmount').value),
                items: document.getElementById('editItems').value
            };
            try {
                var response = await fetch('/api/orders/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                var result = await response.json();
                if (result.success) {
                    bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                    loadStats();
                    loadOrders();
                } else {
                    alert('更新失敗：' + (result.error || ''));
                }
            } catch (error) {
                alert('更新失敗：' + error.message);
            }
        }

        async function deleteOrder(id) {
            if (!confirm('確定要刪除這筆訂單嗎？')) return;
            try {
                var response = await fetch('/api/orders/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: id })
                });
                var result = await response.json();
                if (result.success) {
                    loadStats();
                    loadOrders();
                } else {
                    alert('刪除失敗：' + (result.error || ''));
                }
            } catch (error) {
                alert('刪除失敗：' + error.message);
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

            file_data = None
            media_type = 'image/jpeg'
            for part in parts:
                if b'filename="' not in part:
                    continue
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue
                header = part[:header_end].decode('utf-8', errors='replace')
                file_data = part[header_end + 4:]
                if file_data.endswith(b'\r\n'):
                    file_data = file_data[:-2]
                # 偵測圖片類型
                import re
                fname_match = re.search(r'filename="([^"]+)"', header)
                if fname_match:
                    ext = os.path.splitext(fname_match.group(1))[1].lower()
                    if ext == '.png':
                        media_type = 'image/png'
                    elif ext in ('.webp',):
                        media_type = 'image/webp'
                break

            if not file_data:
                self.send_error_response('No file found')
                return

            # 用 Claude Vision 辨識截圖內容
            orders_found = recognize_orders(file_data, media_type)

            if not orders_found:
                response = json.dumps({
                    'success': True, 'orders': [],
                    'message': '未偵測到訂單資料，請確認是 UberEats 訂單截圖'
                }, ensure_ascii=False)
                self.send_json_response(response)
                return

            # 寫入資料庫（自動去重）
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            added = []
            skipped = []
            for o in orders_found:
                cursor.execute('SELECT id FROM orders WHERE restaurant_name=? AND order_date=? AND amount=?',
                               (o['restaurant_name'], o['order_date'], int(o['amount'])))
                if cursor.fetchone():
                    skipped.append(o['restaurant_name'])
                else:
                    cursor.execute('INSERT INTO orders (restaurant_name, order_date, amount, items) VALUES (?, ?, ?, ?)',
                                   (o['restaurant_name'], o['order_date'], int(o['amount']), o.get('items', '')))
                    added.append(o['restaurant_name'])
            conn.commit()
            conn.close()

            response = json.dumps({
                'success': True,
                'orders': orders_found,
                'added': added,
                'skipped': skipped,
                'message': '辨識到 {} 筆訂單，新增 {} 筆，跳過 {} 筆重複'.format(
                    len(orders_found), len(added), len(skipped))
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
            # 重複檢查：同餐廳 + 同日期 + 同金額 視為重複
            cursor.execute('SELECT id FROM orders WHERE restaurant_name=? AND order_date=? AND amount=?',
                           (data['restaurant_name'], data['order_date'], int(data['amount'])))
            existing = cursor.fetchone()
            if existing:
                conn.close()
                response = json.dumps({'success': False, 'duplicate': True,
                    'error': '此訂單已存在（同餐廳、同日期、同金額）'}, ensure_ascii=False)
                self.send_json_response(response)
                return
            cursor.execute('INSERT INTO orders (restaurant_name, order_date, amount, items) VALUES (?, ?, ?, ?)',
                           (data['restaurant_name'], data['order_date'], int(data['amount']), data['items']))
            conn.commit()
            order_id = cursor.lastrowid
            conn.close()
            response = json.dumps({'success': True, 'id': order_id}, ensure_ascii=False)
            self.send_json_response(response)
        except Exception as e:
            self.send_error_response(str(e))

    def update_order(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('UPDATE orders SET restaurant_name=?, order_date=?, amount=?, items=? WHERE id=?',
                           (data['restaurant_name'], data['order_date'], int(data['amount']), data['items'], int(data['id'])))
            conn.commit()
            conn.close()
            response = json.dumps({'success': True}, ensure_ascii=False)
            self.send_json_response(response)
        except Exception as e:
            self.send_error_response(str(e))

    def delete_order(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM orders WHERE id=?', (int(data['id']),))
            conn.commit()
            conn.close()
            response = json.dumps({'success': True}, ensure_ascii=False)
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
    orders = [
        ('臭名昭彰祖傳酥炸臭豆腐', '2026-04-06', 130, '臭豆腐'),
        ('串本町串燒（原火奴總店）', '2026-03-22', 417, '8份餐點'),
        ('阿俊龍飽', '2026-03-14', 130, '蝦仁炒飯'),
        ('肉蛋吐司創始店 肉蛋中西式早餐店', '2026-03-14', 170, '招牌肉蛋土司、招牌冰奶茶'),
        ('范姜雞肉飯 后里甲后店', '2026-03-09', 166, 'Braised Chicken Rice、Pork Meatballs Soup、Braised Tofu'),
        ('鍋裡GOiN風味湯鍋 台中后里店', '2026-02-26', 226, '火鍋美食鍋'),
        ('一頂燒堡臭豆腐 后里店', '2026-02-11', 140, '酥炸臭豆腐'),
    ]
    added = 0
    for o in orders:
        cursor.execute('SELECT id FROM orders WHERE restaurant_name=? AND order_date=? AND amount=?', (o[0], o[1], o[2]))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO orders (restaurant_name, order_date, amount, items) VALUES (?, ?, ?, ?)', o)
            added += 1
    if added > 0:
        print('已載入 {} 筆 UberEats 訂單（跳過重複）'.format(added))
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
