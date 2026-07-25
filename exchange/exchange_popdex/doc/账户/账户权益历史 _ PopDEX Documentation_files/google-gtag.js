
(function(){
    if(window && window.addEventListener){
        window.addEventListener('load',function(){
            const script = document.createElement('script')
            script.src = 'https://www.googletagmanager.com/gtag/js?id=G-Z8Q93KHR0F'
            script.addEventListener('load', () => {
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('config', 'G-Z8Q93KHR0F');
            })
            document.head.appendChild(script)
        })
    }
})()