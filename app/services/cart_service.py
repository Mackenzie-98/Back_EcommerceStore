"""Cart service with shopping cart business logic"""

from typing import Dict, Any, Optional
from uuid import UUID
from decimal import Decimal

from app.models import Cart, CartItem, ProductVariant, User, Address, Coupon
from app.repositories import BaseRepository, ProductVariantRepository
from app.extensions import db, redis_client


class CartService:
    """Service for shopping cart operations"""
    
    def __init__(self):
        self.cart_repo = CartRepository()
        self.variant_repo = ProductVariantRepository()
    
    def get_or_create_cart(self, user_id: Optional[UUID] = None, 
                          session_id: Optional[str] = None) -> Optional[Cart]:
        """Get existing cart or create new one"""
        if user_id:
            cart = self.cart_repo.find_one_by({'user_id': user_id, 'status': 'active'})
        elif session_id:
            cart = self.cart_repo.find_one_by({'session_id': session_id, 'status': 'active'})
        else:
            return None
        
        if not cart:
            # Create new cart
            cart_data = {
                'user_id': user_id,
                'session_id': session_id,
                'status': 'active'
            }
            cart = self.cart_repo.create(cart_data)
            self.cart_repo.commit()
        
        return cart
    
    def add_to_cart(self, user_id: Optional[UUID], session_id: Optional[str],
                   variant_id: UUID, quantity: int) -> Dict[str, Any]:
        """Add item to cart"""
        # Check if variant exists and is available
        variant = self.variant_repo.get_by_id(variant_id)
        if not variant or not variant.is_active:
            return {
                'success': False,
                'error': 'Product variant not found or unavailable'
            }
        
        # Check stock availability
        if not variant.is_in_stock() or variant.stock < quantity:
            return {
                'success': False,
                'error': f'Only {variant.stock} units available in stock'
            }
        
        try:
            # Get or create cart
            cart = self.get_or_create_cart(user_id, session_id)
            if not cart:
                return {
                    'success': False,
                    'error': 'Unable to create cart'
                }
            
            # Check if item already exists in cart
            existing_item = None
            for item in cart.items:
                if item.variant_id == variant_id:
                    existing_item = item
                    break
            
            if existing_item:
                # Update quantity
                new_quantity = existing_item.quantity + quantity
                if variant.stock < new_quantity:
                    return {
                        'success': False,
                        'error': f'Only {variant.stock} units available in stock'
                    }
                existing_item.quantity = new_quantity
                existing_item.price = variant.price  # Update to current price
            else:
                # Add new item
                cart_item = CartItem(
                    cart_id=cart.id,
                    variant_id=variant_id,
                    quantity=quantity,
                    price=variant.price
                )
                db.session.add(cart_item)
            
            # Extend cart expiration
            cart.extend_expiration()
            
            db.session.commit()
            
            # Track add to cart event
            self._track_cart_event(user_id, session_id, 'add_to_cart', variant_id, quantity)
            
            return {
                'success': True,
                'cart': cart
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': 'Failed to add item to cart'
            }
    
    def update_cart_item(self, user_id: Optional[UUID], session_id: Optional[str],
                        item_id: UUID, quantity: int) -> Dict[str, Any]:
        """Update cart item quantity"""
        try:
            cart = self.get_or_create_cart(user_id, session_id)
            if not cart:
                return {
                    'success': False,
                    'error': 'Cart not found'
                }
            
            # Find cart item
            cart_item = None
            for item in cart.items:
                if item.id == item_id:
                    cart_item = item
                    break
            
            if not cart_item:
                return {
                    'success': False,
                    'error': 'Cart item not found'
                }
            
            if quantity == 0:
                # Remove item
                db.session.delete(cart_item)
            else:
                # Check stock availability
                if cart_item.variant.stock < quantity:
                    return {
                        'success': False,
                        'error': f'Only {cart_item.variant.stock} units available'
                    }
                
                cart_item.quantity = quantity
                cart_item.price = cart_item.variant.price  # Update to current price
            
            # Extend cart expiration
            cart.extend_expiration()
            
            db.session.commit()
            
            return {
                'success': True,
                'cart': cart
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': 'Failed to update cart item'
            }
    
    def remove_from_cart(self, user_id: Optional[UUID], session_id: Optional[str],
                        item_id: UUID) -> Dict[str, Any]:
        """Remove item from cart"""
        return self.update_cart_item(user_id, session_id, item_id, 0)
    
    def clear_cart(self, user_id: Optional[UUID], 
                   session_id: Optional[str]) -> Dict[str, Any]:
        """Clear all items from cart"""
        try:
            cart = self.get_or_create_cart(user_id, session_id)
            if not cart:
                return {
                    'success': False,
                    'error': 'Cart not found'
                }
            
            # Remove all items
            for item in cart.items:
                db.session.delete(item)
            
            db.session.commit()
            
            return {
                'success': True,
                'cart': cart
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': 'Failed to clear cart'
            }
    
    def apply_coupon(self, user_id: Optional[UUID], session_id: Optional[str],
                    coupon_code: str) -> Dict[str, Any]:
        """Apply coupon to cart"""
        try:
            cart = self.get_or_create_cart(user_id, session_id)
            if not cart:
                return {
                    'success': False,
                    'error': 'Cart not found'
                }
            
            # Find coupon
            coupon = db.session.query(Coupon).filter(
                Coupon.code == coupon_code.upper()
            ).first()
            
            if not coupon:
                return {
                    'success': False,
                    'error': 'Invalid coupon code'
                }
            
            # Calculate cart total
            cart_total = cart.get_subtotal()
            
            # Validate coupon
            validation = coupon.is_valid(cart_total, user_id)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': ', '.join(validation['errors'])
                }
            
            # Calculate discount
            discount_amount = coupon.calculate_discount(cart_total)
            
            # Store coupon in cart metadata
            if not hasattr(cart, 'metadata') or cart.metadata is None:
                cart.metadata = {}
            
            cart.metadata.update({
                'coupon_code': coupon_code.upper(),
                'coupon_id': str(coupon.id),
                'discount_amount': float(discount_amount)
            })
            
            db.session.commit()
            
            return {
                'success': True,
                'cart': cart,
                'discount': {
                    'code': coupon_code.upper(),
                    'amount': float(discount_amount),
                    'type': coupon.discount_type
                }
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': 'Failed to apply coupon'
            }
    
    def remove_coupon(self, user_id: Optional[UUID], 
                     session_id: Optional[str]) -> Dict[str, Any]:
        """Remove coupon from cart"""
        try:
            cart = self.get_or_create_cart(user_id, session_id)
            if not cart:
                return {
                    'success': False,
                    'error': 'Cart not found'
                }
            
            # Remove coupon from metadata
            if hasattr(cart, 'metadata') and cart.metadata:
                cart.metadata.pop('coupon_code', None)
                cart.metadata.pop('coupon_id', None)
                cart.metadata.pop('discount_amount', None)
            
            db.session.commit()
            
            return {
                'success': True,
                'cart': cart
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': 'Failed to remove coupon'
            }
    
    def validate_cart(self, user_id: Optional[UUID], 
                     session_id: Optional[str]) -> Dict[str, Any]:
        """Validate cart items for stock and pricing"""
        cart = self.get_or_create_cart(user_id, session_id)
        if not cart:
            return {
                'valid': False,
                'errors': ['Cart not found']
            }
        
        validation_result = cart.validate_items()
        
        if validation_result['updated_items']:
            try:
                db.session.commit()
            except:
                db.session.rollback()
        
        return {
            'valid': validation_result['valid'],
            'errors': validation_result['errors'],
            'warnings': [f"Price updated for {item.variant.name}" 
                        for item in validation_result['updated_items']],
            'cart': cart
        }
    
    def calculate_totals(self, user_id: Optional[UUID], session_id: Optional[str],
                        shipping_address_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Calculate cart totals including tax and shipping"""
        try:
            cart = self.get_or_create_cart(user_id, session_id)
            if not cart:
                return {
                    'success': False,
                    'error': 'Cart not found'
                }
            
            if cart.is_empty():
                return {
                    'success': True,
                    'totals': {
                        'subtotal': 0,
                        'tax': 0,
                        'shipping': 0,
                        'discount': 0,
                        'total': 0
                    }
                }
            
            # Calculate subtotal
            subtotal = cart.get_subtotal()
            
            # Calculate discount
            discount = Decimal('0.00')
            if hasattr(cart, 'metadata') and cart.metadata and 'discount_amount' in cart.metadata:
                discount = Decimal(str(cart.metadata['discount_amount']))
            
            # Calculate tax (simplified - 8% for example)
            tax_rate = Decimal('0.08')
            tax = (subtotal - discount) * tax_rate
            
            # Calculate shipping
            shipping = self._calculate_shipping(cart, shipping_address_id)
            
            # Calculate total
            total = subtotal + tax + shipping - discount
            
            return {
                'success': True,
                'totals': {
                    'subtotal': float(subtotal),
                    'tax': float(tax),
                    'shipping': float(shipping),
                    'discount': float(discount),
                    'total': float(total),
                    'items_count': cart.get_total_quantity()
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': 'Failed to calculate totals'
            }
    
    def _calculate_shipping(self, cart: Cart, 
                           shipping_address_id: Optional[UUID] = None) -> Decimal:
        """Calculate shipping cost"""
        subtotal = cart.get_subtotal()
        
        # Free shipping over $50
        if subtotal >= Decimal('50.00'):
            return Decimal('0.00')
        
        # Standard shipping rate
        return Decimal('9.99')
    
    def _track_cart_event(self, user_id: Optional[UUID], session_id: Optional[str],
                         event_type: str, variant_id: UUID, quantity: int):
        """Track cart-related events"""
        try:
            from app.models import UserEvent
            event = UserEvent(
                user_id=user_id,
                session_id=session_id,
                event_type=event_type,
                entity_type='product_variant',
                entity_id=variant_id,
                metadata={'quantity': quantity}
            )
            db.session.add(event)
            db.session.commit()
        except Exception:
            db.session.rollback()


class CartRepository(BaseRepository):
    """Repository for cart operations"""
    
    def __init__(self):
        super().__init__(Cart)


# Import repositories
 