let quarantineChartInstance = null;
let rulesChartInstance = null;
let uploadedFilePath = null;

function initCharts(qData = {}, rData = {}) {
    const qCtx = document.getElementById('quarantineChart').getContext('2d');
    if (quarantineChartInstance) quarantineChartInstance.destroy();

    quarantineChartInstance = new Chart(qCtx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(qData).length ? Object.keys(qData) : ['لا يوجد أخطاء'],
            datasets: [{
                data: Object.values(qData).length ? Object.values(qData) : [1],
                backgroundColor: ['#ef4444', '#f59e0b', '#8b5cf6', '#3b82f6', '#10b981', '#ec4899', '#6366f1']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: 'توزيع أسباب العزل (Quarantine Reasons)', color: '#fff', font: { family: 'Tajawal', size: 14 } },
                legend: { position: 'bottom', labels: { color: '#9ca3af', font: { family: 'Tajawal', size: 11 } } }
            }
        }
    });

    const rCtx = document.getElementById('rulesChart').getContext('2d');
    if (rulesChartInstance) rulesChartInstance.destroy();

    rulesChartInstance = new Chart(rCtx, {
        type: 'bar',
        data: {
            labels: Object.keys(rData).length ? Object.keys(rData) : ['لا يوجد تصحيحات'],
            datasets: [{
                label: 'عدد المرات',
                data: Object.values(rData).length ? Object.values(rData) : [0],
                backgroundColor: '#3b82f6',
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: 'أكثر قواعد التنظيف المطبقة (Applied Rules Audit)', color: '#fff', font: { family: 'Tajawal', size: 14 } },
                legend: { display: false }
            },
            scales: {
                x: { ticks: { color: '#9ca3af', font: { family: 'Tajawal', size: 10 } } },
                y: { ticks: { color: '#9ca3af' } }
            }
        }
    });
}

function updateAutoRoutingBadge(sizeMb, rowsStr = null) {
    const sizeText = document.getElementById('detectedSizeText');
    const rowsText = document.getElementById('detectedRowsText');
    const badgeContainer = document.getElementById('detectedLoaderBadge');
    const summaryBadgeContainer = document.getElementById('loaderBadgeContainer');

    const sizeStr = sizeMb > 1024 ? (sizeMb / 1024).toFixed(2) + ' GB' : sizeMb.toFixed(2) + ' MB';
    sizeText.innerText = 'حجم الملف: ' + sizeStr;

    if (rowsStr && rowsText) {
        rowsText.innerText = 'إجمالي السجلات: ' + rowsStr;
    }

    if (sizeMb > 200) {
        const sparkHTML = '<span class="loader-badge badge-spark"><i class="fa-solid fa-bolt"></i> PySpark Loader (لأن الحجم > 200MB)</span>';
        badgeContainer.innerHTML = sparkHTML;
        if (summaryBadgeContainer) summaryBadgeContainer.innerHTML = sparkHTML;
    } else {
        const pythonHTML = '<span class="loader-badge badge-python"><i class="fa-brands fa-python"></i> Python Batch Loader (لأن الحجم <= 200MB)</span>';
        badgeContainer.innerHTML = pythonHTML;
        if (summaryBadgeContainer) summaryBadgeContainer.innerHTML = pythonHTML;
    }
}

function onSelectChanged() {
    uploadedFilePath = null;
    const select = document.getElementById('fileSelect');
    const opt = select.options[select.selectedIndex];
    if (opt) {
        const sizeMb = parseFloat(opt.getAttribute('data-size')) || 0;
        const rowsStr = opt.getAttribute('data-rowsstr') || 'غير محدد';
        updateAutoRoutingBadge(sizeMb, rowsStr);
    }
}

function onFileUploaded(event) {
    const file = event.target.files[0];
    if (!file) return;

    document.getElementById('uploadBoxText').innerText = 'تم التحديد: ' + file.name;
    const sizeMb = file.size / (1024 * 1024);
    updateAutoRoutingBadge(sizeMb);

    // رفع الملف للسيرفر
    const formData = new FormData();
    formData.append('file', file);

    const statusMsg = document.getElementById('statusMessage');
    statusMsg.innerText = 'جاري رفع الملف إلى المجلد وحساب عدد السجلات...';

    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            uploadedFilePath = data.file_path;
            updateAutoRoutingBadge(data.size_mb, data.rows_str);
            statusMsg.innerText = 'تم رفع الملف وحساب حجمه وسجلاته بنجاح!';
        } else {
            alert('فشل الرفع: ' + data.message);
        }
    });
}

function fetchStatus() {
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            const statusBox = document.getElementById('statusBox');
            const statusMsg = document.getElementById('statusMessage');
            const progressFill = document.getElementById('progressFill');
            const runBtn = document.getElementById('runBtn');
            const liveBox = document.getElementById('liveProgressBox');

            if (data.status === 'running') {
                statusMsg.innerText = data.message;
                progressFill.style.width = data.progress_percent + '%';
                statusBox.className = 'status-box status-running';
                runBtn.disabled = true;
                runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري المعالجة...';

                liveBox.style.display = 'block';
                document.getElementById('cntProcessed').innerText = (data.processed || 0).toLocaleString();
                document.getElementById('cntRemaining').innerText = (data.remaining || 0).toLocaleString();
                document.getElementById('cntTotal').innerText = (data.total_raw || 0).toLocaleString();
            } else if (data.status === 'success') {
                statusMsg.innerText = data.message;
                progressFill.style.width = '100%';
                statusBox.className = 'status-box status-success';
                runBtn.disabled = false;
                runBtn.innerHTML = '<i class="fa-solid fa-play"></i> بدء المعالجة التلقائية';

                if (data.processed && data.total_raw) {
                    liveBox.style.display = 'block';
                    document.getElementById('cntProcessed').innerText = (data.processed || 0).toLocaleString();
                    document.getElementById('cntRemaining').innerText = '0';
                    document.getElementById('cntTotal').innerText = (data.total_raw || 0).toLocaleString();
                }
            } else if (data.status === 'error') {
                statusMsg.innerText = data.message;
                progressFill.style.width = '0%';
                statusBox.className = 'status-box status-error';
                runBtn.disabled = false;
                runBtn.innerHTML = '<i class="fa-solid fa-play"></i> بدء المعالجة التلقائية';
            }

            // Live RAM stats update
            if (data.ram_stats) {
                document.getElementById('resRamUsed').innerText = data.ram_stats.used_gb + ' GB (' + data.ram_stats.percent_used + '% مستخدمة)';
                document.getElementById('resRamFree').innerText = data.ram_stats.available_gb + ' GB متبقية حرة للجهاز';
            }

            if (data.last_result) {
                renderResults(data.last_result);
            }
        });
}

function renderResults(res) {
    document.getElementById('valRaw').innerText = (res.run_raw_count || 0).toLocaleString();
    document.getElementById('valValid').innerText = (res.run_valid_count || 0).toLocaleString();
    document.getElementById('valCorrected').innerText = (res.run_corrected_count || 0).toLocaleString();
    document.getElementById('valQuarantine').innerText = (res.run_quarantine_count || 0).toLocaleString();

    document.getElementById('durationVal').innerText = res.duration_seconds + ' ثانية';
    document.getElementById('runIdVal').innerText = res.run_id || '-';

    // Batch Size Highlight
    if (res.resources && res.resources.dynamic_batch_size) {
        const bSize = res.resources.dynamic_batch_size.toLocaleString();
        document.getElementById('batchSizeHighlight').innerText = bSize + ' سجل/دفعة';
        document.getElementById('resBatch').innerText = bSize + ' سجل/دفعة';
    }

    // Dynamic Resources Update
    if (res.resources) {
        document.getElementById('resCores').innerText = res.resources.cores_allocated + ' أنوية (مخصصة من ' + res.resources.total_cores + ')';
    }

    const loaderContainer = document.getElementById('loaderBadgeContainer');
    if (res.loader_used === 'spark_loader') {
        loaderContainer.innerHTML = '<span class="loader-badge badge-spark"><i class="fa-solid fa-bolt"></i> PySpark Loader (ملف كبير)</span>';
    } else {
        loaderContainer.innerHTML = '<span class="loader-badge badge-python"><i class="fa-brands fa-python"></i> Python Batch Loader (Streaming)</span>';
    }

    // Resumption Banner Display
    const resumeBanner = document.getElementById('resumeBanner');
    if (res.is_resumed) {
        resumeBanner.style.display = 'block';
        document.getElementById('resumePrevRows').innerText = (res.previously_processed_rows || 0).toLocaleString();
        document.getElementById('resumeNewRows').innerText = (res.new_rows_added || 0).toLocaleString();
    } else {
        resumeBanner.style.display = 'none';
    }

    const banner = document.getElementById('formulaBanner');
    const formulaExpr = document.getElementById('formulaExpr');
    banner.style.display = 'flex';
    formulaExpr.innerText = res.consistency_formula;

    initCharts(res.top_quarantine_reasons || {}, res.top_correction_rules || {});
}

function toggleRulesSection() {
    const body = document.getElementById('rulesConfigBody');
    const icon = document.getElementById('rulesToggleIcon');
    if (body.style.display === 'none') {
        body.style.display = 'block';
        icon.innerHTML = '<i class="fa-solid fa-chevron-up"></i>';
    } else {
        body.style.display = 'none';
        icon.innerHTML = '<i class="fa-solid fa-chevron-down"></i>';
    }
}

function toggleAllRules(state) {
    const ruleIds = [
        'rule_phone', 'rule_currency', 'rule_date', 'rule_email',
        'rule_numeric', 'rule_text', 'rule_items', 'rule_total_recalc',
        'q_order_id', 'q_customer_id', 'q_date', 'q_items_json',
        'q_items_empty', 'q_price_unknown', 'q_negative'
    ];
    ruleIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.checked = state;
    });
}

function startPipeline() {
    const selectedFile = document.getElementById('fileSelect').value;
    const targetPath = uploadedFilePath || selectedFile;
    const reset = document.getElementById('resetDb').checked;

    const maxRowsVal = document.getElementById('maxRowsInput').value.trim();
    const maxRows = maxRowsVal ? parseInt(maxRowsVal, 10) : null;

    const enabledRules = {
        rule_phone: document.getElementById('rule_phone').checked,
        rule_currency: document.getElementById('rule_currency').checked,
        rule_date: document.getElementById('rule_date').checked,
        rule_email: document.getElementById('rule_email').checked,
        rule_numeric: document.getElementById('rule_numeric').checked,
        rule_text: document.getElementById('rule_text').checked,
        rule_items: document.getElementById('rule_items').checked,
        rule_total_recalc: document.getElementById('rule_total_recalc').checked,
    };

    const enabledQuarantines = {
        q_order_id: document.getElementById('q_order_id').checked,
        q_customer_id: document.getElementById('q_customer_id').checked,
        q_date: document.getElementById('q_date').checked,
        q_items_json: document.getElementById('q_items_json').checked,
        q_items_empty: document.getElementById('q_items_empty').checked,
        q_price_unknown: document.getElementById('q_price_unknown').checked,
        q_negative: document.getElementById('q_negative').checked,
    };

    fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            file_path: targetPath,
            reset: reset,
            max_rows: maxRows,
            enabled_rules: enabledRules,
            enabled_quarantines: enabledQuarantines
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'started') {
            fetchStatus();
        } else {
            alert(data.message);
        }
    });
}

// Initial setup
onSelectChanged();
initCharts();
setInterval(fetchStatus, 2000);
fetchStatus();
