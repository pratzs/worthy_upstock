from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def process_upstock_order(self, data):
        """
        Parses the specific Upstock order.created JSON payload
        and creates a native Odoo Sales Order.
        """
        order_details = data.get('orderDetails', {})
        
        try:
            # 1. Find or Create the Customer
            raw_buyer_name = order_details.get('buyerName', 'Unknown Upstock Customer')
            clean_buyer_name = raw_buyer_name.replace('🥪 ', '').strip()
            
            partner = self.env['res.partner'].search([('name', '=ilike', clean_buyer_name)], limit=1)
            
            if not partner:
                _logger.info(f"Upstock Webhook: Creating new customer {clean_buyer_name}")
                partner = self.env['res.partner'].create({
                    'name': clean_buyer_name,
                    'ref': order_details.get('buyerId', ''),
                })

            # 2. Prepare the Sales Order Lines
            order_lines = []
            for item in order_details.get('lines', []):
                product_code = item.get('productCode')
                quantity = item.get('quantity', 1)
                price = item.get('unitAmount', {}).get('amount', 0.0)
                
                product = self.env['product.product'].search([('default_code', '=', product_code)], limit=1)
                
                if product:
                    order_lines.append((0, 0, {
                        'product_id': product.id,
                        'product_uom_qty': quantity,
                        'price_unit': price,
                    }))
                else:
                    _logger.warning(f"Upstock Webhook: Product code {product_code} not found in Odoo database.")

            # 3. Create the Sales Order
            if order_lines:
                new_order = self.create({
                    'partner_id': partner.id,
                    'order_line': order_lines,
                    'client_order_ref': f"Upstock-{order_details.get('orderId')}",
                    'origin': 'Upstock Integration',
                })
                _logger.info(f"Successfully created Odoo SO {new_order.name} from Upstock Order {order_details.get('orderId')}.")
                return new_order
            else:
                _logger.error("Upstock Webhook: No valid order lines could be matched. Order creation aborted.")
                return False

        except Exception as e:
            _logger.error(f"Error processing Upstock order: {str(e)}")
            raise
