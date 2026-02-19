# DataForge.io Backend API
# Simple Flask API for pipeline management

from flask import Flask, jsonify, request, g
from dataforge_core.config import get_config
from dataforge_core.metadata_framework import pipeline_registry
from dataforge_core.logging_config import setup_logging
import logging

app = Flask(__name__)
logger = setup_logging(name="dataforge_api", level="INFO")

# Load config
config = get_config()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'environment': config.environment.value,
        'version': '0.1.0'
    })


@app.route('/pipelines', methods=['GET'])
def list_pipelines():
    """List all registered pipelines."""
    pipelines = pipeline_registry.list_all()
    return jsonify({
        'count': len(pipelines),
        'pipelines': [
            {
                'name': name,
                'version': config.version,
                'mode': config.mode.value,
                'schedule': config.schedule,
                'enabled': config.enabled
            }
            for name, config in pipelines.items()
        ]
    })


@app.route('/pipelines/<pipeline_name>', methods=['GET'])
def get_pipeline(pipeline_name):
    """Get pipeline details."""
    pipeline = pipeline_registry.get(pipeline_name)
    if not pipeline:
        return jsonify({'error': 'Pipeline not found'}), 404
    
    return jsonify(pipeline.dict(exclude_none=True))


@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Get Prometheus metrics."""
    from dataforge_core.observability import MetricsCollector
    
    metrics = MetricsCollector()
    return metrics.get_metrics(), 200, {'Content-Type': 'text/plain'}


@app.route('/config', methods=['GET'])
def get_configuration():
    """Get current configuration (excluding secrets)."""
    return jsonify(config.dict(exclude={'cloud': {'access_key', 'secret_key'}}))


@app.errorhandler(404)
def not_found(error):
    """404 handler."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """500 handler."""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
