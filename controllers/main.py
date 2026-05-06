import json
from odoo import http
from odoo.http import request
from svix.webhooks import Webhook

class UpstockWebhookReceiver(http.Controller):
    
    # type='http' and csrf=False are strictly required for receiving external webhooks
    @http.route('/api/upstock/webhook', type='http', auth='public', methods=['POST'], csrf=False)
    def receive_upstock_webhook(self, **kwargs):
        # 1. Grab raw data and headers for Svix signature verification
        raw_payload = request.httprequest.data
        headers = request.httprequest.headers
        
        # 2. Retrieve the Svix secret stored in Odoo's System Parameters
        svix_secret = request.env['ir.config_parameter'].sudo().get_param('upstock.webhook_secret')
        
        if not svix_secret:
            return request.make_response(
                json.dumps({'error': 'Webhook secret not configured in system parameters'}), 
                status=500, 
                headers={'Content-Type': 'application/json'}
            )

        # 3. Verify the payload using the Svix library
        try:
            wh = Webhook(svix_secret)
            wh.verify(raw_payload, headers)
        except Exception as e:
            return request.make_response(
                json.dumps({'error': 'Invalid Signature'}), 
                status=401,
                headers={'Content-Type': 'application/json'}
            )
            
        # 4. Parse the verified payload and process the event
        try:
            payload = json.loads(raw_payload.decode('utf-8'))
            event_type = payload.get('type')
            
            # Route the event based on what Upstock sends
            if event_type == 'order.created':
                # We use sudo() because this public route has no logged-in user context.
                # Note: You will need to define `process_upstock_order` in your sale.order model
                request.env['sale.order'].sudo().process_upstock_order(payload.get('data'))
                
            # Return standard HTTP 200 JSON success response so Upstock knows it was received
            return request.make_response(
                json.dumps({'status': 'success'}), 
                headers={'Content-Type': 'application/json'}
            )
            
        except Exception as e:
            # Returning a 400 status ensures Svix queues a retry for failed processing
            return request.make_response(
                json.dumps({'error': str(e)}), 
                status=400, 
                headers={'Content-Type': 'application/json'}
            )
