require 'json'

module Jekyll
  module AcaUtil
    def self.load_json(site, path)
      file = File.join(site.source, path)
      return [] unless File.exist?(file)
      JSON.parse(File.read(file, encoding: 'utf-8'))
    rescue => e
      Jekyll.logger.warn "AcaGenerator:", "#{path} 로드 실패: #{e.message}"
      []
    end

    def self.rawdata_dir(site)
      File.join(site.source, '_rawdata')
    end
  end

  # ── 데이터 로드 (한 번만) ──────────────────────────────
  class AcaDataGenerator < Generator
    safe true
    priority :highest

    def generate(site)
      return if site.data['aca_all']

      dir = AcaUtil.rawdata_dir(site)
      shard_files = Dir.glob(File.join(dir, 'leaf_*.json'))
      all_items = []
      by_do = Hash.new { |h, k| h[k] = [] }

      shard_files.each do |f|
        do_short = File.basename(f, '.json').sub('leaf_', '')
        items = JSON.parse(File.read(f, encoding: 'utf-8'))
        by_do[do_short] = items
        all_items.concat(items)
      end

      site.data['aca_all'] = all_items
      site.data['aca_by_do'] = by_do
      Jekyll.logger.info "AcaGenerator:", "총 #{all_items.size}개 학원 로드 (#{by_do.size}개 시도)"
    end
  end

  # ── 시도 인덱스 페이지 ─────────────────────────────────
  class DoIndexPageGenerator < Generator
    safe true
    priority :normal

    def generate(site)
      by_do = site.data['aca_by_do'] || {}
      by_do.each do |do_short, items|
        site.pages << DoIndexPage.new(site, do_short, items)
      end
      Jekyll.logger.info "AcaGenerator:", "시도 페이지 #{by_do.size}개 생성"
    end
  end

  class DoIndexPage < Page
    def initialize(site, do_short, items)
      @site = site
      @base = site.source
      @dir  = "region/#{do_short}"
      @name = 'index.html'
      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'do.html')

      by_sigungu = Hash.new(0)
      items.each { |it| by_sigungu[it['sigungu']] += 1 }
      sigungu_list = by_sigungu.map { |nm, cnt| { 'name' => nm, 'count' => cnt } }.sort_by { |s| -s['count'] }

      self.data['doShort'] = do_short
      self.data['sigunguList'] = sigungu_list
      self.data['totalCount'] = items.size
      self.data['layout'] = 'do'
      self.data['title'] = "#{do_short} 학원·교습소 정보 — 시군구별 목록"
      self.data['description'] = "#{do_short} 지역 학원·교습소 #{items.size}곳의 위치와 수강료 정보를 시군구별로 확인하세요."
    end
  end

  # ── 시군구 페이지 (동/리프 목록) ────────────────────────
  class SigunguPageGenerator < Generator
    safe true
    priority :normal

    def generate(site)
      by_do = site.data['aca_by_do'] || {}
      count = 0
      by_do.each do |do_short, items|
        grouped = Hash.new { |h, k| h[k] = [] }
        items.each { |it| grouped[it['sigungu']] << it }
        grouped.each do |sigungu, list|
          site.pages << SigunguPage.new(site, do_short, sigungu, list)
          count += 1
        end
      end
      Jekyll.logger.info "AcaGenerator:", "시군구 페이지 #{count}개 생성"
    end
  end

  class SigunguPage < Page
    def initialize(site, do_short, sigungu, items)
      @site = site
      @base = site.source
      @dir  = "region/#{do_short}/#{sigungu}"
      @name = 'index.html'
      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'sigungu.html')

      by_dong = Hash.new(0)
      items.each { |it| by_dong[it['dong']] += 1 }
      dong_list = by_dong.map { |nm, cnt| { 'name' => nm, 'count' => cnt } }.sort_by { |d| -d['count'] }

      self.data['doShort'] = do_short
      self.data['sigungu'] = sigungu
      self.data['dongList'] = dong_list
      self.data['totalCount'] = items.size
      self.data['layout'] = 'sigungu'
      self.data['title'] = "#{do_short} #{sigungu} 학원·교습소 목록 (#{items.size}곳)"
      self.data['description'] = "#{do_short} #{sigungu} 학원·교습소 #{items.size}곳의 위치, 교습과목, 수강료 정보를 확인하세요."
    end
  end

  # ── 동(리프) 페이지 - 실제 학원 카드 목록 ────────────────
  class DongPageGenerator < Generator
    safe true
    priority :normal

    def generate(site)
      by_do = site.data['aca_by_do'] || {}
      count = 0
      by_do.each do |do_short, items|
        grouped = Hash.new { |h, k| h[k] = [] }
        items.each { |it| grouped[[it['sigungu'], it['dong']]] << it }
        grouped.each do |(sigungu, dong), list|
          site.pages << DongPage.new(site, do_short, sigungu, dong, list)
          count += 1
        end
      end
      Jekyll.logger.info "AcaGenerator:", "동(리프) 페이지 #{count}개 생성"
    end
  end

  class DongPage < Page
    def initialize(site, do_short, sigungu, dong, items)
      @site = site
      @base = site.source
      @dir  = "region/#{do_short}/#{sigungu}/#{dong}"
      @name = 'index.html'
      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'dong.html')

      self.data['doShort'] = do_short
      self.data['sigungu'] = sigungu
      self.data['dongName'] = dong
      self.data['items'] = items.sort_by { |it| it['name'] }
      self.data['totalCount'] = items.size
      self.data['layout'] = 'dong'
      self.data['title'] = "#{do_short} #{sigungu} #{dong} 학원·교습소 (#{items.size}곳) — 수강료 정보"
      self.data['description'] = "#{do_short} #{sigungu} #{dong} 학원·교습소 #{items.size}곳의 교습과목과 실제 수강료를 확인하세요."
    end
  end
end
