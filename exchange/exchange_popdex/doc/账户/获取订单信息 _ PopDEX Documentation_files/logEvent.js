try {
  window.$log = new Log({
    app_id: "popdex_web_01",
    app_name: "popdex_web",
  },[{
    path: /\/api-doc\//g,
    event_tracking:'bg_web_exchange_api_doc_page',
    event_tracking_id: 'b4913',
    business1: 'open api',
  }]);
} catch {}
