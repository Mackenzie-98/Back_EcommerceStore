#!/usr/bin/env python3
"""Seed script to populate the database with sample data"""

from app import create_app
from app.models import db, Category, Product, ProductVariant, ProductImage
from app.extensions import db as db_instance
import uuid

def create_sample_data():
    app = create_app()
    
    with app.app_context():
        # Clear existing data
        ProductImage.query.delete()
        ProductVariant.query.delete()
        Product.query.delete()
        Category.query.delete()
        
        # Create categories
        categories = {
            'hombres': Category(
                id=uuid.uuid4(),
                name='Hombres',
                slug='hombres',
                description='Ropa para hombres',
                is_active=True,
                sort_order=1
            ),
            'mujeres': Category(
                id=uuid.uuid4(),
                name='Mujeres', 
                slug='mujeres',
                description='Ropa para mujeres',
                is_active=True,
                sort_order=2
            ),
            'ninos': Category(
                id=uuid.uuid4(),
                name='Niños',
                slug='ninos', 
                description='Ropa para niños',
                is_active=True,
                sort_order=3
            )
        }
        
        for category in categories.values():
            db_instance.session.add(category)
        
        db_instance.session.commit()
        
        # Create sample products
        products = [
            {
                'name': 'Camiseta Básica Hombre',
                'slug': 'camiseta-basica-hombre',
                'description': 'Camiseta de algodón 100% para hombre',
                'brand': 'BasicBrand',
                'category': categories['hombres'],
                'price': 25000,
                'compare_price': 35000,
                'stock': 50,
                'image_url': '/images/product-1.png'
            },
            {
                'name': 'Jeans Clásicos Hombre',
                'slug': 'jeans-clasicos-hombre', 
                'description': 'Jeans de alta calidad para hombre',
                'brand': 'DenimCo',
                'category': categories['hombres'],
                'price': 120000,
                'compare_price': 150000,
                'stock': 30,
                'image_url': '/images/product-2.png'
            },
            {
                'name': 'Vestido Elegante Mujer',
                'slug': 'vestido-elegante-mujer',
                'description': 'Vestido elegante para ocasiones especiales',
                'brand': 'Elegance',
                'category': categories['mujeres'],
                'price': 180000,
                'compare_price': 220000,
                'stock': 25,
                'image_url': '/images/product-4.png'
            },
            {
                'name': 'Blusa Casual Mujer',
                'slug': 'blusa-casual-mujer',
                'description': 'Blusa casual y cómoda para el día a día',
                'brand': 'CasualWear',
                'category': categories['mujeres'],
                'price': 45000,
                'compare_price': 55000,
                'stock': 40,
                'image_url': '/images/product-5.png'
            },
            {
                'name': 'Conjunto Deportivo Niño',
                'slug': 'conjunto-deportivo-nino',
                'description': 'Conjunto deportivo para niños activos',
                'brand': 'KidsSport',
                'category': categories['ninos'],
                'price': 35000,
                'compare_price': 45000,
                'stock': 35,
                'image_url': '/images/product-6.png'
            },
            {
                'name': 'Camisa Formal Hombre',
                'slug': 'camisa-formal-hombre',
                'description': 'Camisa formal para oficina y eventos',
                'brand': 'FormalWear',
                'category': categories['hombres'],
                'price': 85000,
                'compare_price': 95000,
                'stock': 20,
                'image_url': '/images/product-7.png'
            },
            {
                'name': 'Falda Plisada Mujer',
                'slug': 'falda-plisada-mujer',
                'description': 'Falda plisada elegante y versátil',
                'brand': 'Elegance',
                'category': categories['mujeres'],
                'price': 65000,
                'compare_price': 75000,
                'stock': 28,
                'image_url': '/images/product-8.png'
            }
        ]
        
        for product_data in products:
            product = Product(
                id=uuid.uuid4(),
                sku=f"SKU-{uuid.uuid4().hex[:8].upper()}",
                name=product_data['name'],
                slug=product_data['slug'],
                description=product_data['description'],
                short_description=product_data['description'][:100] + '...',
                category_id=product_data['category'].id,
                brand=product_data['brand'],
                tags=['ropa', 'moda'],
                is_active=True,
                is_featured=len(products) <= 3,  # First 3 are featured
                weight=0.5,
                dimensions={'length': 30, 'width': 20, 'height': 5}
            )
            
            db_instance.session.add(product)
            db_instance.session.flush()  # Get the product ID
            
            # Create variant
            variant = ProductVariant(
                id=uuid.uuid4(),
                product_id=product.id,
                sku=f"VAR-{uuid.uuid4().hex[:8].upper()}",
                name="Talla M",
                price=product_data['price'],
                compare_at_price=product_data['compare_price'],
                cost=product_data['price'] * 0.6,  # 40% margin
                stock=product_data['stock'],
                attributes={'size': 'M', 'color': 'Azul'},
                images=[],
                is_active=True
            )
            
            db_instance.session.add(variant)
            
            # Create image
            image = ProductImage(
                id=uuid.uuid4(),
                product_id=product.id,
                url=product_data['image_url'],
                alt_text=product_data['name'],
                is_primary=True,
                sort_order=0
            )
            
            db_instance.session.add(image)
        
        db_instance.session.commit()
        
        print("✅ Sample data created successfully!")
        print(f"Categories: {Category.query.count()}")
        print(f"Products: {Product.query.count()}")
        print(f"Variants: {ProductVariant.query.count()}")
        print(f"Images: {ProductImage.query.count()}")

if __name__ == '__main__':
    create_sample_data() 