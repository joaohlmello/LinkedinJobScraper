from datetime import datetime
import json
from flask_sqlalchemy import SQLAlchemy

# Instância SQLAlchemy para compartilhar com main.py
db = SQLAlchemy()

class ProcessedBatch(db.Model):
    """
    Modelo para armazenar informações de lotes de URLs processados.
    """
    id = db.Column(db.Integer, primary_key=True)
    batch_index = db.Column(db.Integer, nullable=False)
    urls = db.Column(db.Text, nullable=False)  # Armazenado como JSON
    results_html = db.Column(db.Text, nullable=True)
    df_json = db.Column(db.Text, nullable=True)
    has_error = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """
        Converte o modelo para um dicionário.
        """
        try:
            urls_list = json.loads(self.urls) if self.urls else []
        except:
            urls_list = []
            
        return {
            'id': self.id,
            'batch_index': self.batch_index,
            'urls': urls_list,
            'results_html': self.results_html,
            'df_json': self.df_json,
            'has_error': self.has_error,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else ''
        }

class IgnoredURL(db.Model):
    """
    Modelo para armazenar URLs que devem ser ignoradas no processamento.
    """
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1024), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)