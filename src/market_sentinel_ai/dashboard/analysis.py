# ruff: noqa: E501

from __future__ import annotations


def render_prediction_analytics() -> str:
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Sentinel AI · Análisis</title>
  <style>
    :root { color-scheme: light; font-family: Inter, Segoe UI, Arial, sans-serif; color: #102a43; background: #f4f7f9; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    header { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 18px 32px; background: #fff; border-bottom: 1px solid #d9e2ec; }
    h1 { margin: 0; font-size: 24px; }
    h2 { margin: 0 0 14px; font-size: 18px; }
    h3 { margin: 0 0 10px; font-size: 15px; }
    .nav { display: flex; gap: 8px; flex-wrap: wrap; }
    .nav a { color: #0b7285; text-decoration: none; border: 1px solid #b8c7d1; padding: 8px 12px; font-size: 13px; background: #fff; }
    .nav a.active { color: #fff; background: #0b7285; border-color: #0b7285; }
    main { max-width: 1440px; margin: 0 auto; padding: 24px 32px 48px; }
    .intro { display: flex; justify-content: space-between; align-items: end; gap: 20px; margin-bottom: 18px; }
    .intro p { margin: 6px 0 0; color: #52606d; font-size: 13px; max-width: 780px; }
    .filters, .panel { background: #fff; border: 1px solid #d9e2ec; padding: 16px; }
    .filters { display: flex; gap: 12px; align-items: end; flex-wrap: wrap; margin-bottom: 18px; }
    label { display: flex; flex-direction: column; gap: 5px; color: #52606d; font-size: 12px; }
    input, select, button { min-height: 36px; border: 1px solid #9fb3c8; padding: 7px 10px; font: inherit; font-size: 13px; background: #fff; }
    button { color: #fff; background: #0b7285; border-color: #0b7285; cursor: pointer; font-weight: 700; }
    button:hover { background: #095c6b; }
    .metrics { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px; }
    .metric { min-height: 82px; border-left: 3px solid #0b7285; }
    .metric.good { border-color: #16803c; }
    .metric.bad { border-color: #b42318; }
    .metric span { display: block; color: #627d98; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
    .metric strong { display: block; margin-top: 9px; font-size: 22px; color: #102a43; }
    .grid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 18px; margin-bottom: 18px; }
    .table-wrap { overflow: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { padding: 10px 8px; border-bottom: 1px solid #e5ecf2; text-align: left; white-space: nowrap; }
    th { color: #52606d; font-weight: 700; background: #f8fafc; }
    .positive { color: #16803c; font-weight: 700; }
    .negative { color: #b42318; font-weight: 700; }
    .pending { color: #9c6b00; font-weight: 700; }
    .muted { color: #627d98; }
    .status { min-height: 20px; margin: 0 0 12px; color: #52606d; font-size: 13px; }
    @media (max-width: 1000px) { .metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); } .grid { grid-template-columns: 1fr; } }
    @media (max-width: 620px) { header { align-items: flex-start; flex-direction: column; padding: 16px; } main { padding: 18px 16px 32px; } .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  </style>
</head>
<body>
  <header>
    <h1>Market Sentinel AI · Análisis de predicciones</h1>
    <nav class="nav" aria-label="Navegación principal">
      <a href="/">Centro de control</a>
      <a class="active" href="/analysis">Análisis de predicciones</a>
    </nav>
  </header>
  <main>
    <div class="intro">
      <div>
        <h2>Historial de aciertos y fallos</h2>
        <p>Las predicciones se guardan automáticamente para toda la watchlist. La tabla incluye todos los horizontes configurados, aunque todavía no tengan muestras. Una predicción pasa a resuelta cuando llega su horizonte y se compara contra el precio real disponible.</p>
      </div>
    </div>
    <form class="filters" id="filters">
      <label>Producto o acción<input id="symbol" placeholder="Todos" maxlength="24"></label>
      <label>Timeframe interno<select id="timeframe"><option value="">Todos</option><option value="1m">1m</option><option value="5m">5m</option><option value="15m">15m</option><option value="1h">1h</option><option value="1d">1d</option></select></label>
      <label>Horizonte<select id="window"><option value="">Todos</option><option value="1m">1 minuto</option><option value="5m">5 minutos</option><option value="10m">10 minutos</option><option value="30m">30 minutos</option><option value="1h">1 hora</option><option value="2h">2 horas</option><option value="6h">6 horas</option><option value="12h">12 horas</option><option value="1d">1 día</option><option value="1w">1 semana</option><option value="1mo">1 mes</option><option value="3mo">3 meses</option><option value="6mo">6 meses</option><option value="1y">1 año</option><option value="3y">3 años</option></select></label>
      <label>Estado<select id="status"><option value="">Todos</option><option value="resolved">Resueltas</option><option value="pending">Pendientes</option></select></label>
      <label>Muestras máximas<select id="limit"><option value="500">500</option><option value="2000">2.000</option><option value="5000" selected>5.000</option><option value="20000">20.000</option></select></label>
      <button type="submit">Actualizar análisis</button>
      <button type="button" class="secondary" id="reset-history">Poner aciertos a cero</button>
    </form>
    <p class="status" id="status-message" aria-live="polite">Cargando análisis...</p>
    <section class="metrics" id="metrics"></section>
    <div class="grid">
      <section class="panel"><h2>Resultado por horizonte</h2><div class="table-wrap"><table><thead><tr><th>Horizonte</th><th>Total</th><th>Resueltas</th><th>Aciertos</th><th>Fallos</th><th>Acierto</th><th>Retorno real medio</th></tr></thead><tbody id="window-rows"><tr><td colspan="7" class="muted">Cargando...</td></tr></tbody></table></div></section>
      <section class="panel"><h2>Resultado por producto</h2><div class="table-wrap"><table><thead><tr><th>Producto</th><th>Total</th><th>Resueltas</th><th>Aciertos</th><th>Acierto</th><th>Retorno real medio</th></tr></thead><tbody id="symbol-rows"><tr><td colspan="6" class="muted">Cargando...</td></tr></tbody></table></div></section>
    </div>
    <section class="panel"><h2>Últimas predicciones</h2><div class="table-wrap"><table><thead><tr><th>Producto</th><th>Horizonte</th><th>Dirección</th><th>Confianza</th><th>Referencia</th><th>Real</th><th>Retorno</th><th>Resultado</th><th>Generada</th><th>Vencía</th></tr></thead><tbody id="recent-rows"><tr><td colspan="10" class="muted">Cargando...</td></tr></tbody></table></div></section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const safe = (value) => value === null || value === undefined ? '-' : String(value);
    const pct = (value) => value === null || value === undefined ? '-' : `${Number(value).toFixed(1)}%`;
    const bps = (value) => value === null || value === undefined ? '-' : `${Number(value).toFixed(1)} bps`;
    const money = (value) => value === null || value === undefined ? '-' : Number(value).toFixed(4);
    function metric(label, value, className = '') { return `<div class="panel metric ${className}"><span>${label}</span><strong>${safe(value)}</strong></div>`; }
    function resultClass(value) { return value === true ? 'positive' : value === false ? 'negative' : 'pending'; }
    function accuracyClass(value) { return value === null || value === undefined ? 'pending' : Number(value) >= 50 ? 'positive' : 'negative'; }
    function aggregateRow(item, includeProduct) {
      const accuracy = item.accuracy_pct;
      const cls = accuracyClass(accuracy);
      return `<tr><td>${includeProduct ? safe(item.key) : safe(item.key)}</td><td>${item.total}</td><td>${item.resolved}</td><td>${item.correct}</td><td>${item.incorrect ?? '-'}</td><td class="${cls}">${pct(accuracy)}</td><td>${bps(item.avg_actual_return_bps)}</td></tr>`;
    }
    function render(payload) {
      const overallAccuracyClass = payload.accuracy_pct !== null && payload.accuracy_pct >= 50 ? 'good' : 'bad';
      $('metrics').innerHTML = [
        metric('Predicciones', payload.total), metric('Pendientes', payload.pending, 'pending'),
        metric('Resueltas', payload.resolved), metric('Aciertos', payload.correct, 'good'),
        metric('Fallos', payload.incorrect, 'bad'), metric('Acierto general', pct(payload.accuracy_pct), overallAccuracyClass),
        metric('Mejor horizonte', safe(payload.best_window), 'good'), metric('Retorno real medio', bps(payload.avg_actual_return_bps))
      ].join('');
      $('window-rows').innerHTML = payload.by_window.length ? payload.by_window.map((item) => aggregateRow(item, false)).join('') : '<tr><td colspan="7" class="muted">Sin resultados para estos filtros.</td></tr>';
      $('symbol-rows').innerHTML = payload.by_symbol.length ? payload.by_symbol.map((item) => `<tr><td>${safe(item.key)}</td><td>${item.total}</td><td>${item.resolved}</td><td>${item.correct}</td><td class="${accuracyClass(item.accuracy_pct)}">${pct(item.accuracy_pct)}</td><td>${bps(item.avg_actual_return_bps)}</td></tr>`).join('') : '<tr><td colspan="6" class="muted">Sin resultados para estos filtros.</td></tr>';
      $('recent-rows').innerHTML = payload.recent.length ? payload.recent.map((item) => `<tr><td>${safe(item.symbol)}</td><td>${safe(item.window)}</td><td>${safe(item.direction)}</td><td>${(Number(item.confidence) * 100).toFixed(1)}%</td><td>${money(item.reference_price)}</td><td>${money(item.actual_price)}</td><td>${bps(item.actual_return_bps)}</td><td class="${resultClass(item.correct)}">${item.status === 'pending' ? 'PENDIENTE' : item.correct ? 'ACIERTO' : 'FALLO'}</td><td>${safe(item.generated_at)}</td><td>${safe(item.due_at)}</td></tr>`).join('') : '<tr><td colspan="10" class="muted">Sin predicciones registradas todavía.</td></tr>';
    }
    async function load() {
      const params = new URLSearchParams();
      [['symbol', $('symbol').value.trim()], ['timeframe', $('timeframe').value], ['window', $('window').value], ['status', $('status').value], ['limit', $('limit').value]].forEach(([key, value]) => { if (value) params.set(key, value); });
      $('status-message').textContent = 'Actualizando resultados...';
      const response = await fetch(`/api/v1/prediction-analytics?${params}`);
      if (!response.ok) { $('status-message').textContent = 'No se pudo cargar el análisis.'; return; }
      render(await response.json());
      $('status-message').textContent = `Actualizado ${new Date().toLocaleString()}. Las pendientes se resolverán automáticamente al vencer su horizonte.`;
    }
    $('filters').addEventListener('submit', (event) => { event.preventDefault(); load().catch(() => { $('status-message').textContent = 'No se pudo cargar el análisis.'; }); });
    $('reset-history').addEventListener('click', async () => {
      if (!window.confirm('Se borrará el historial de predicciones y sus aciertos/fallos. Las operaciones simuladas no se borrarán. ¿Continuar?')) return;
      $('status-message').textContent = 'Reiniciando historial...';
      const response = await fetch('/api/v1/predictions/reset', {method: 'POST'});
      if (!response.ok) { $('status-message').textContent = 'No se pudo reiniciar el historial.'; return; }
      const payload = await response.json();
      $('status-message').textContent = `Historial reiniciado: ${payload.deleted} predicciones eliminadas.`;
      await load();
    });
    load().catch(() => { $('status-message').textContent = 'No se pudo cargar el análisis.'; });
    window.setInterval(() => load().catch(() => {}), 30000);
  </script>
</body>
</html>"""
